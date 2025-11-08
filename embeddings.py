#!/usr/bin/env python3
"""
Generate embeddings using Google Embeddings API - SIMPLE & RELIABLE VERSION
- No complex retry logic
- Simple 1-second delays between requests (safe)
- Uses Google text-embedding-3-large (3072 dimensions)
"""


import os
import time
from neo4j import GraphDatabase
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()


# Google client
client = GoogleGenerativeAIEmbeddings(model="gemini-embedding-001")


# Neo4j connection
neo4j_driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
)



def get_embedding(text: str) -> list[float] | None:
    """
    Generate an embedding using Google.
    Returns the list of floats (3072 dimensions), or None on failure.
    """
    try:
        response = client.embed_query(text)
        return response

    except Exception as e:
        print(f"⚠️ Embedding failed: {e}")
        return None



def embed_functions():
    """Embed functions - replace text embeddings with vector embeddings"""
    print("\n" + "="*60)
    print("EMBEDDING FUNCTIONS")
    print("="*60)

    with neo4j_driver.session() as session:
        result = session.run("""
            MATCH (f:Function) 
            WHERE f.embedding_semantics IS NOT NULL
            RETURN f.id, f.name, f.embedding_semantics
            LIMIT 1000
        """)
        
        nodes = result.data()
        text_nodes = [n for n in nodes if isinstance(n['f.embedding_semantics'], str)]
        total_count = len(text_nodes)

        print(f"Total functions to embed: {total_count}\n")

        if total_count == 0:
            print("✓ All functions already embedded!")
            return

        embedded, skipped = 0, 0

        for i, func_data in enumerate(text_nodes, 1):
            func_id = func_data['f.id']
            func_name = func_data['f.name']
            text_to_embed = func_data['f.embedding_semantics'] or ""  # This is the semantic text

            print(f"[{i}/{total_count}] Embedding {func_name}... ", end="", flush=True)
            embedding = get_embedding(text_to_embed)

            if embedding:
                session.run("""
                    MATCH (f:Function {id: $id})
                    SET f.embedding_semantics = $embedding,
                        f.embedded_text = $text,
                        f.embedding_status = 'embedded',
                        f.embedding_timestamp = datetime()
                """, id=func_id, embedding=embedding, text=text_to_embed)
                print("✓")
                embedded += 1
            else:
                session.run("""
                    MATCH (f:Function {id: $id})
                    SET f.embedding_status = 'failed'
                """, id=func_id)
                print("✗")
                skipped += 1

            time.sleep(1.0)

        print(f"\n✓ Embedded: {embedded}")
        print(f"✗ Failed: {skipped}")


def embed_methods():
    """Embed methods - replace text embeddings with vector embeddings"""
    print("\n" + "="*60)
    print("EMBEDDING METHODS")
    print("="*60)

    with neo4j_driver.session() as session:
        result = session.run("""
            MATCH (m:Method) 
            WHERE m.embedding_semantics IS NOT NULL
            RETURN m.id, m.name, m.embedding_semantics
            LIMIT 1000
        """)
        
        nodes = result.data()
        text_nodes = [n for n in nodes if isinstance(n['m.embedding_semantics'], str)]
        total_count = len(text_nodes)

        print(f"Total methods to embed: {total_count}\n")

        if total_count == 0:
            print("✓ All methods already embedded!")
            return

        embedded, skipped = 0, 0

        for i, method_data in enumerate(text_nodes, 1):
            method_id = method_data['m.id']
            method_name = method_data['m.name']
            text_to_embed = method_data['m.embedding_semantics'] or ""

            print(f"[{i}/{total_count}] Embedding {method_name}... ", end="", flush=True)
            embedding = get_embedding(text_to_embed)

            if embedding:
                session.run("""
                    MATCH (m:Method {id: $id})
                    SET m.embedding_semantics = $embedding,
                        m.embedded_text = $text,
                        m.embedding_status = 'embedded',
                        m.embedding_timestamp = datetime()
                """, id=method_id, embedding=embedding, text=text_to_embed)
                print("✓")
                embedded += 1
            else:
                session.run("""
                    MATCH (m:Method {id: $id})
                    SET m.embedding_status = 'failed'
                """, id=method_id)
                print("✗")
                skipped += 1

            time.sleep(1.0)

        print(f"\n✓ Embedded: {embedded}")
        print(f"✗ Failed: {skipped}")


def embed_files():
    """Embed files - replace text embeddings with vector embeddings"""
    print("\n" + "="*60)
    print("EMBEDDING FILES")
    print("="*60)

    with neo4j_driver.session() as session:
        result = session.run("""
            MATCH (f:File) 
            WHERE f.embedding_semantics IS NOT NULL
            RETURN f.id, f.name, f.embedding_semantics
            LIMIT 1000
        """)
        
        nodes = result.data()
        text_nodes = [n for n in nodes if isinstance(n['f.embedding_semantics'], str)]
        total_count = len(text_nodes)

        print(f"Total files to embed: {total_count}\n")

        if total_count == 0:
            print("✓ All files already embedded!")
            return

        embedded, skipped = 0, 0

        for i, file_data in enumerate(text_nodes, 1):
            file_id = file_data['f.id']
            file_name = file_data['f.name']
            text_to_embed = file_data['f.embedding_semantics'] or ""

            print(f"[{i}/{total_count}] Embedding {file_name}... ", end="", flush=True)
            embedding = get_embedding(text_to_embed)

            if embedding:
                session.run("""
                    MATCH (f:File {id: $id})
                    SET f.embedding_semantics = $embedding,
                        f.embedded_text = $text,
                        f.embedding_status = 'embedded',
                        f.embedding_timestamp = datetime()
                """, id=file_id, embedding=embedding, text=text_to_embed)
                print("✓")
                embedded += 1
            else:
                session.run("""
                    MATCH (f:File {id: $id})
                    SET f.embedding_status = 'failed'
                """, id=file_id)
                print("✗")
                skipped += 1

            time.sleep(1.0)

        print(f"\n✓ Embedded: {embedded}")
        print(f"✗ Failed: {skipped}")


def embed_classes():
    """Embed classes - replace text embeddings with vector embeddings"""
    print("\n" + "="*60)
    print("EMBEDDING CLASSES")
    print("="*60)

    with neo4j_driver.session() as session:
        result = session.run("""
            MATCH (c:Class) 
            WHERE c.embedding_semantics IS NOT NULL
            RETURN c.id, c.name, c.embedding_semantics
            LIMIT 1000
        """)
        
        nodes = result.data()
        text_nodes = [n for n in nodes if isinstance(n['c.embedding_semantics'], str)]
        total_count = len(text_nodes)

        print(f"Total classes to embed: {total_count}\n")

        if total_count == 0:
            print("✓ All classes already embedded!")
            return

        embedded, skipped = 0, 0

        for i, class_data in enumerate(text_nodes, 1):
            class_id = class_data['c.id']
            class_name = class_data['c.name']
            text_to_embed = class_data['c.embedding_semantics'] or ""

            print(f"[{i}/{total_count}] Embedding {class_name}... ", end="", flush=True)
            embedding = get_embedding(text_to_embed)

            if embedding:
                session.run("""
                    MATCH (c:Class {id: $id})
                    SET c.embedding_semantics = $embedding,
                        c.embedded_text = $text,
                        c.embedding_status = 'embedded',
                        c.embedding_timestamp = datetime()
                """, id=class_id, embedding=embedding, text=text_to_embed)
                print("✓")
                embedded += 1
            else:
                session.run("""
                    MATCH (c:Class {id: $id})
                    SET c.embedding_status = 'failed'
                """, id=class_id)
                print("✗")
                skipped += 1

            time.sleep(1.0)

        print(f"\n✓ Embedded: {embedded}")
        print(f"✗ Failed: {skipped}")



def verify():
    """Verify all embeddings"""
    print("\n" + "="*60)
    print("VERIFICATION")
    print("="*60 + "\n")

    with neo4j_driver.session() as session:
        # Count by embedding status
        functions_embedded = session.run(
            "MATCH (f:Function) WHERE f.embedding_status = 'embedded' RETURN count(f) as cnt"
        ).single()['cnt']
        
        methods_embedded = session.run(
            "MATCH (m:Method) WHERE m.embedding_status = 'embedded' RETURN count(m) as cnt"
        ).single()['cnt']
        
        files_embedded = session.run(
            "MATCH (f:File) WHERE f.embedding_status = 'embedded' RETURN count(f) as cnt"
        ).single()['cnt']
        
        classes_embedded = session.run(
            "MATCH (c:Class) WHERE c.embedding_status = 'embedded' RETURN count(c) as cnt"
        ).single()['cnt']

        total_embedded = functions_embedded + methods_embedded + files_embedded + classes_embedded
        
        print(f"✅ SUCCESSFULLY EMBEDDED:")
        print(f"Functions: {functions_embedded}")
        print(f"Methods: {methods_embedded}")
        print(f"Files: {files_embedded}")
        print(f"Classes: {classes_embedded}")
        print(f"TOTAL: {total_embedded}\n")
        

        # Also show nodes without embeddings
        functions_not_embedded = session.run(
            "MATCH (f:Function) WHERE f.embedding_status IS NULL OR f.embedding_status <> 'embedded' RETURN count(f) as cnt"
        ).single()['cnt']

        methods_not_embedded = session.run(
            "MATCH (m:Method) WHERE m.embedding_status IS NULL OR m.embedding_status <> 'embedded' RETURN count(m) as cnt"
        ).single()['cnt']

        classes_not_embedded = session.run(
            "MATCH (c:Class) WHERE c.embedding_status IS NULL OR c.embedding_status <> 'embedded' RETURN count(c) as cnt"
        ).single()['cnt']

        files_not_embedded = session.run(
            "MATCH (f:File) WHERE f.embedding_status IS NULL OR f.embedding_status <> 'embedded' RETURN count(f) as cnt"
        ).single()['cnt']

        print(f"⏭️  NOT EMBEDDED (no docstring):")
        print(f"Functions: {functions_not_embedded}")
        print(f"Methods: {methods_not_embedded}")
        print(f"Classes: {classes_not_embedded}")
        print(f"Files: {files_not_embedded}")




def close_driver():
    """Close Neo4j driver"""
    global neo4j_driver
    if neo4j_driver:
        neo4j_driver.close()



if __name__ == "__main__":
    print("\n" + "="*60)
    print("Google EMBEDDING - SIMPLE & RELIABLE")
    print("="*60)
    print("\nStrategy:")
    print("  • 1 second delay between requests")
    print("  • = 60 requests/minute (safe)")
    print("  • Simple, reliable, no complex logic")
    print("="*60)

    try:
        embed_functions()
        embed_methods()
        embed_files()
        embed_classes()
        verify()

        print("\n" + "="*60)
        print("✓ DONE!")
        print("="*60)

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        print("Run again to resume from where it stopped")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        close_driver()