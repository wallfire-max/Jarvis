import os
import json
import requests
import datetime
import math

MEMORY_FILE = "C:\\Users\\Jaswa\\OneDrive\\Desktop\\rudra\\memory.json"
SEMANTIC_FILE = "C:\\Users\\Jaswa\\OneDrive\\Desktop\\rudra\\semantic_memory.json"

def get_api_key():
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, 'r') as f:
                memory = json.load(f)
            return memory.get("gemini_key", "").strip()
    except Exception as e:
        print(f"Error loading key for semantic memory: {e}")
    return ""

def get_embedding_gemini(text, api_key):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": "models/text-embedding-004",
            "content": {
                "parts": [{"text": text}]
            }
        }
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        res.raise_for_status()
        res_json = res.json()
        return res_json.get("embedding", {}).get("values", [])
    except Exception as e:
        print(f"Gemini embedding API failed: {e}. Falling back to local BoW vector.")
        return None

def get_local_bow_vector(text):
    # Simple local fallback using normalized bag-of-words term frequencies
    import re
    words = re.findall(r'\w+', text.lower())
    stopwords = {'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', "you're", "you've", "you'll", "you'd", 'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she', "she's", 'her', 'hers', 'herself', 'it', "it's", 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves', 'what', 'which', 'who', 'whom', 'this', 'that', "that'll", 'these', 'those', 'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for', 'with', 'about', 'against', 'between', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'can', 'will', 'just', 'don', "don't", 'should', "should've", 'now', 'd', 'll', 'm', 'o', 're', 've', 'y', 'ain', 'aren', "aren't", 'couldn', "couldn't", 'didn', "didn't", 'doesn', "doesn't", 'hadn', "hadn't", 'hasn', "hasn't", 'haven', "haven't", 'isn', "isn't", 'ma', 'mightn', "mightn't", 'mustn', "mustn't", 'needn', "needn't", 'shan', "shan't", 'shouldn', "shouldn't", 'wasn', "wasn't", 'weren', "weren't", 'won', "won't", 'wouldn', "wouldn't"}
    
    tf = {}
    for w in words:
        if w not in stopwords and len(w) > 1:
            tf[w] = tf.get(w, 0) + 1
            
    # L2 normalize the bag of words dictionary
    sq_sum = sum(v*v for v in tf.values())
    if sq_sum == 0:
        return {}
    norm = math.sqrt(sq_sum)
    for k in tf:
        tf[k] = tf[k] / norm
    return tf

def cosine_similarity_bow(vec1, vec2):
    # Vector similarity for dictionary vectors (sparse bag of words)
    if not vec1 or not vec2:
        return 0.0
    dot_product = 0.0
    for k in vec1:
        if k in vec2:
            dot_product += vec1[k] * vec2[k]
    # Vectors are already L2 normalized, so similarity is just the dot product
    return dot_product

def cosine_similarity_dense(v1, v2):
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)

def load_semantic_memories():
    if not os.path.exists(SEMANTIC_FILE):
        return []
    try:
        with open(SEMANTIC_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading semantic database: {e}")
        return []

def save_semantic_memories(memories):
    try:
        with open(SEMANTIC_FILE, 'w') as f:
            json.dump(memories, f, indent=2)
    except Exception as e:
        print(f"Error saving semantic database: {e}")

def store_memory(text, m_type="fact"):
    if not text.strip():
        return False
        
    api_key = get_api_key()
    embedding = None
    local_vector = None
    
    if api_key:
        embedding = get_embedding_gemini(text, api_key)
        
    if embedding is None:
        local_vector = get_local_bow_vector(text)
        
    memories = load_semantic_memories()
    
    # Avoid exact duplicates
    for m in memories:
        if m.get("text", "").lower().strip() == text.lower().strip():
            return True
            
    new_memory = {
        "text": text,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": m_type,
        "embedding": embedding,
        "local_vector": local_vector
    }
    
    memories.append(new_memory)
    save_semantic_memories(memories)
    return True

def query_semantic_memory(query_text, top_k=3, threshold=0.25):
    if not query_text.strip():
        return []
        
    api_key = get_api_key()
    memories = load_semantic_memories()
    if not memories:
        return []
        
    query_emb = None
    query_bow = None
    
    if api_key:
        query_emb = get_embedding_gemini(query_text, api_key)
        
    if query_emb is None:
        query_bow = get_local_bow_vector(query_text)
        
    scored_memories = []
    for m in memories:
        sim = 0.0
        # If we have Gemini embeddings on both query and stored memory
        if query_emb and m.get("embedding"):
            sim = cosine_similarity_dense(query_emb, m["embedding"])
        # Else fall back to bag-of-words similarity
        else:
            # Recompute BoW vectors if missing
            m_bow = m.get("local_vector")
            if m_bow is None:
                m_bow = get_local_bow_vector(m["text"])
            if query_bow is None:
                query_bow = get_local_bow_vector(query_text)
            sim = cosine_similarity_bow(query_bow, m_bow)
            
        if sim >= threshold:
            scored_memories.append((sim, m))
            
    # Sort descending
    scored_memories.sort(key=lambda x: x[0], reverse=True)
    return [m for score, m in scored_memories[:top_k]]

def clear_semantic_memories():
    save_semantic_memories([])
    return True

if __name__ == "__main__":
    # Quick test
    print("Testing Semantic Memory engine...")
    store_memory("Jaswanth likes to write Python code in vscode in the evening.")
    store_memory("Jaswanth usually drinks black coffee when studying.")
    
    results = query_semantic_memory("What does Jaswanth coding preferences?", top_k=1)
    print("Search results:")
    for r in results:
        print(f"- {r['text']} (stored on {r['timestamp']})")
