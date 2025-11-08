#!/usr/bin/env python3
"""
Neo4j Aura Chatbot Agent - Simple Client

Direct connection using:
- CLIENT_ID (OAuth)
- CLIENT_SECRET (OAuth)
- ENDPOINT_URL (Agent endpoint)

No PROJECT_ID or AGENT_ID needed.
"""

import json
import logging
import os
import httpx
import asyncio
from typing import Optional
from dotenv import load_dotenv
import time

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global configuration
client_id: Optional[str] = None
client_secret: Optional[str] = None
endpoint_url: Optional[str] = None
bearer_token: Optional[str] = None
token_expiry: float = 0


def _load_config():
    """Load configuration from .env file"""
    global client_id, client_secret, endpoint_url
    
    load_dotenv()
    
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    endpoint_url = os.getenv("ENDPOINT_URL")
    
    if not all([client_id, client_secret, endpoint_url]):
        raise ValueError(
            "Required environment variables not found:\n"
            "CLIENT_ID, CLIENT_SECRET, ENDPOINT_URL\n\n"
            "Get these from Neo4j Aura console agent settings"
        )
    
    logger.info(f"Configuration loaded successfully")
    logger.info(f"Endpoint: {endpoint_url}")


async def _get_bearer_token() -> None:
    """Get OAuth bearer token from Neo4j"""
    global bearer_token, token_expiry
    
    auth_url = "https://api.neo4j.io/oauth/token"
    
    async with httpx.AsyncClient() as client:
        try:
            logger.info("Requesting OAuth token...")
            
            response = await client.post(
                auth_url,
                auth=(client_id, client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={"grant_type": "client_credentials"},
                timeout=30.0
            )
            
            if response.status_code != 200:
                logger.error(f"Token request failed: {response.status_code}")
                logger.error(f"Response: {response.text}")
                response.raise_for_status()
            
            token_data = response.json()
            bearer_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 3600)
            token_expiry = time.time() + expires_in - 60  # Refresh 1 min before expiry
            
            if not bearer_token:
                raise ValueError("No access token in response")
            
            logger.info(f"Bearer token obtained (expires in {expires_in}s)")
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP Error: {e}")
            raise Exception(f"Failed to get bearer token: {e}")
        except Exception as e:
            logger.error(f"Token error: {e}")
            raise


async def _ensure_token():
    """Ensure token is still valid, refresh if needed"""
    global bearer_token, token_expiry
    
    if bearer_token is None or time.time() > token_expiry:
        await _get_bearer_token()


async def _query_aura_agent(question: str) -> str:
    """
    Query Neo4j Aura agent using the endpoint URL
    
    Sends:
    - POST to endpoint_url
    - JSON body: {"input": question}
    - Authorization: Bearer token
    """
    global bearer_token, endpoint_url
    
    # Ensure token is valid
    await _ensure_token()
    
    logger.info(f"Querying agent: {endpoint_url}")
    logger.info(f"Question: {question}")
    
    async with httpx.AsyncClient() as client:
        try:
            # Send request to agent endpoint
            response = await client.post(
                endpoint_url,
                headers={
                    "Authorization": f"Bearer {bearer_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                json={"input": question},
                timeout=120.0  # 2 minute timeout for complex queries
            )
            
            logger.info(f"Response status: {response.status_code}")
            
            # Handle 401 - token expired
            if response.status_code == 401:
                logger.warning("Token expired, refreshing...")
                await _get_bearer_token()
                
                # Retry request with new token
                response = await client.post(
                    endpoint_url,
                    headers={
                        "Authorization": f"Bearer {bearer_token}",
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    },
                    json={"input": question},
                    timeout=120.0
                )
            
            # Handle other errors
            if response.status_code >= 400:
                logger.error(f"Error {response.status_code}: {response.text}")
                response.raise_for_status()
            
            # Parse response
            result = response.json()
            
            logger.info(f"Response type: {type(result)}")
            
            # HANDLE FORMAT 1: {"content": [{"type": "text", "text": "answer"}, ...]}
            if isinstance(result, dict) and "content" in result:
                content = result.get("content", [])
                logger.info(f"Content items: {len(content)}")
                
                # Collect all text responses
                text_parts = []
                for i, item in enumerate(content):
                    logger.info(f"Item {i}: type={item.get('type')}")
                    
                    if item.get("type") == "text":
                        text = item.get("text", "")
                        if text:
                            text_parts.append(text)
                
                # Join all text parts
                if text_parts:
                    final_answer = "\n".join(text_parts)
                    logger.info(f"Extracted answer length: {len(final_answer)}")
                    return final_answer
                else:
                    logger.warning("No text content found in response")
                    return "No response text found in agent response"
            
            # HANDLE FORMAT 2: Direct string response
            if isinstance(result, str):
                logger.info(f"String response: {len(result)} chars")
                return result
            
            # HANDLE FORMAT 3: {"answer": "text"} or {"response": "text"}
            if isinstance(result, dict):
                if "answer" in result:
                    return result.get("answer", "")
                if "response" in result:
                    return result.get("response", "")
                if "text" in result:
                    return result.get("text", "")
            
            # FALLBACK: Return JSON
            logger.warning("Could not parse response, returning JSON")
            return json.dumps(result, indent=2)
            
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            logger.error(error_msg)
            raise Exception(f"Agent query failed: {error_msg}")
        except httpx.TimeoutException:
            logger.error("Request timeout - query too complex or slow")
            raise Exception("Agent request timed out. Query may be too complex.")
        except httpx.HTTPError as e:
            logger.error(f"HTTP Error: {e}")
            raise Exception(f"Network error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Response is not valid JSON: {e}")
            raise Exception(f"Agent returned invalid JSON: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise


async def main():
    """Main CLI loop"""
    try:
        # Load configuration
        _load_config()
        
        # Get initial token
        logger.info("Initializing agent connection...")
        await _get_bearer_token()
        
        # Print header
        print("\n" + "="*80)
        print("NEO4J AURA AGENT - LOCAL CLIENT")
        print("="*80)
        print("\nConnected! Ask your questions. Type 'exit' to quit.\n")
        
        # Interactive loop
        while True:
            try:
                # Get user input
                user_input = input("You: ").strip()
                
                # Check for exit
                if user_input.lower() in ['exit', 'quit', 'bye', 'q']:
                    print("\nGoodbye!")
                    break
                
                # Skip empty input
                if not user_input:
                    continue
                
                # Show that agent is thinking
                print("\n[Agent thinking...]")
                
                # Query agent
                try:
                    answer = await _query_aura_agent(user_input)
                    print(f"\nAgent: {answer}\n")
                    
                except asyncio.TimeoutError:
                    print("\n[Agent request timed out - query too complex]\n")
                except Exception as e:
                    print(f"\n[Agent error: {str(e)}]\n")
                    logger.error(f"Agent error: {str(e)}")
                
            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"\nError: {str(e)}\n")
                logger.error(f"Error: {str(e)}")
    
    except Exception as e:
        print(f"\nFatal error: {str(e)}")
        logger.error(f"Fatal error: {str(e)}")
        print("\nConfiguration required in .env:")
        print("  CLIENT_ID - OAuth client ID")
        print("  CLIENT_SECRET - OAuth client secret")
        print("  ENDPOINT_URL - Agent endpoint URL from Neo4j console")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)