import asyncio

from qdrant_client import QdrantClient

from app.application.services.chunker import Chunker
from app.application.services.corpus_indexing import CorpusIndexingService
from app.infrastructure.ai.tokenizers import SimpleTokenizer
from app.infrastructure.embeddings import OllamaEmbeddings
from app.infrastructure.retrieval.qdrant_vector_index import QdrantVectorIndex


async def run_test():
    # Use embedded Qdrant directly
    client = QdrantClient(path='data/qdrant')

    # Set up the service with real components, passing the client directly
    chunker = Chunker(SimpleTokenizer(), max_tokens_per_chunk=512)
    embeddings = OllamaEmbeddings()
    # Create QdrantVectorIndex with the embedded client and known dimension
    index = QdrantVectorIndex(collection_name='legal_corpus', dimension=768, client=client)

    service = CorpusIndexingService(chunker=chunker, embeddings=embeddings, index=index)

    text = (
        'The supplier shall be liable for all direct damages. '
        'Indirect damages are excluded unless gross negligence is proven.\n\n'
        'The customer may terminate the agreement for material breach.'
    )

    print('Indexing with matter_id=matter-1, source_id=contract-1')
    count = await service.index_text('matter-1', 'contract-1', text)
    print(f'Indexed {count} chunks')

    # Verify Qdrant
    info = client.get_collection('legal_corpus')
    vectors = info.config.params.vectors
    print('\nCollection: legal_corpus')
    print(f'Vector size: {vectors.size}')
    print(f'Distance: {vectors.distance}')

    count_result = client.count('legal_corpus')
    print(f'Point count: {count_result}')

    # Check payloads
    hits = client.search('legal_corpus', query_vector=[0.1]*768, limit=3)
    print(f'\nSearch results: {len(hits)}')
    for i, hit in enumerate(hits):
        print(f'  Hit {i+1}:')
        print(f'    id={hit.id}')
        print(f'    score={hit.score}')
        payload = hit.payload or {}
        print(f'    chunk_id={payload.get("chunk_id")}')
        print(f'    matter_id={payload.get("matter_id")}')
        print(f'    source_id={payload.get("source_id")}')
        print(f'    text={payload.get("text")[:80]}...')
        print(f'    page_number={payload.get("page_number")}')
        print(f'    start_offset={payload.get("start_offset")}')
        print(f'    end_offset={payload.get("end_offset")}')


asyncio.run(run_test())
