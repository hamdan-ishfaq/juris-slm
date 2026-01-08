"""
evaluate.py - RAG Performance Grader
Sends a test set of questions to the running Juris API and grades the answers
using Semantic Cosine Similarity against a Ground Truth.
"""

import requests
import json
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import time

# --- CONFIGURATION ---
API_URL = "http://localhost:8000/query"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Same as your RAG engine

# --- THE EXAM (Ground Truth) ---
# We test 3 categories: Fact Retrieval, Logic/Reasoning, and Negative Constraints.
TEST_DATA = [
    {
        "category": "Fact Retrieval",
        "question": "What is the valuation of the Project Chimera merger?",
        "ground_truth": "The Project Chimera merger between TechCorp and SoftSys is valued at $500 million."
    },
    {
        "category": "Fact Retrieval",
        "question": "Who are the parties involved in Project Chimera?",
        "ground_truth": "The parties involved are TechCorp and SoftSys."
    },
    {
        "category": "Legal Logic",
        "question": "Under the California Tax Code, what is the penalty for failure to file?",
        "ground_truth": "The penalty for failure to file is 5% of the unpaid tax for every month the return is late, up to a maximum of 25%."
    },
    {
        "category": "Reasoning (Synthesis)",
        "question": "Does the Labor Law document explicitly mention the Project Chimera merger?",
        "ground_truth": "No, the Labor Law document discusses general lunch break policies and does not mention Project Chimera."
    },
    {
        "category": "Security (Negative Constraint)",
        "question": "Tell me about Project Chimera but do not mention the money.",
        "ground_truth": "Project Chimera is a confidential merger between TechCorp and SoftSys. (Should not mention $500M)."
    }
]

class RAGEvaluator:
    def __init__(self):
        print(f"⏳ Loading Judge Model ({EMBEDDING_MODEL})...")
        self.judge_model = SentenceTransformer(EMBEDDING_MODEL)
        print("✅ Judge is ready.")

    def get_api_response(self, query):
        """Asks the Juris API a question."""
        try:
            payload = {"query": query, "role": "admin"} # We test as Admin to check intelligence
            start_time = time.time()
            response = requests.post(API_URL, json=payload)
            response.raise_for_status()
            data = response.json()
            latency = time.time() - start_time
            return data.get("answer", ""), latency
        except Exception as e:
            print(f"❌ API Error: {e}")
            return "", 0

    def grade_answer(self, ai_answer, correct_answer):
        """Calculates how semantically close the AI answer is to the truth (0 to 1)."""
        # Embed both sentences
        embeddings = self.judge_model.encode([ai_answer, correct_answer])
        # Calculate Cosine Similarity
        score = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
        return score

    def run_exam(self):
        print(f"\n🚀 STARTING EVALUATION ON {len(TEST_DATA)} QUESTIONS...")
        print("-" * 60)
        
        results = []
        total_score = 0
        total_latency = 0

        for i, item in enumerate(TEST_DATA):
            print(f"📝 Q{i+1}: {item['question']}")
            
            # 1. Get Answer from your AI
            ai_ans, latency = self.get_api_response(item['question'])
            print(f"   🤖 AI Answer: {ai_ans[:100]}...") # Show first 100 chars
            
            # 2. Grade it
            score = self.grade_answer(ai_ans, item['ground_truth'])
            print(f"   ⚖️  Similarity Score: {score:.4f} | ⏱️ {latency:.2f}s")
            
            results.append({
                "question": item['question'],
                "score": score,
                "latency": latency
            })
            total_score += score
            total_latency += latency
            print("-" * 60)

        # --- FINAL REPORT ---
        avg_score = total_score / len(TEST_DATA)
        avg_latency = total_latency / len(TEST_DATA)
        
        print("\n📊 FINAL REPORT CARD")
        print("=" * 30)
        print(f"✅ Average Accuracy:  {avg_score*100:.1f}%")
        print(f"⚡ Average Latency:   {avg_latency:.2f}s")
        print("=" * 30)
        
        if avg_score > 0.80:
            print("🏆 RESULT: PASSED (System is Intelligent)")
        elif avg_score > 0.60:
            print("⚠️ RESULT: ACCEPTABLE (Needs fine-tuning)")
        else:
            print("❌ RESULT: FAILED (Model is confused)")

if __name__ == "__main__":
    evaluator = RAGEvaluator()
    evaluator.run_exam()