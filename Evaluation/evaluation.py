import json
import re
import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from difflib import SequenceMatcher
from typing import Dict, List, Tuple, Optional
import numpy as np
from collections import defaultdict

DB_CONFIG = {
    'username': 'admin',
    'password': 'UPZLcrTX3n9XVb3&',
    'host': 'northwind.cfamiqo2obcc.us-east-2.rds.amazonaws.com',
    'database': 'Northwind'
}

quoted_password = quote_plus(DB_CONFIG['password'])
CONN_STRING = (
    f"mssql+pyodbc://{DB_CONFIG['username']}:{quoted_password}"
    f"@{DB_CONFIG['host']}/{DB_CONFIG['database']}?driver=ODBC+Driver+17+for+SQL+Server"
)

engine = create_engine(CONN_STRING)

def normalize_sql(sql: str) -> str:
    sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
    sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
    sql = re.sub(r'\s+', ' ', sql.strip().lower())
    sql = re.sub(r'\s*=\s*', ' = ', sql)
    sql = re.sub(r'\s*,\s*', ', ', sql)
    sql = re.sub(r'\s*\(\s*', '(', sql)
    sql = re.sub(r'\s*\)\s*', ')', sql)
    return sql

def tokenize_sql(sql: str) -> List[str]:
    tokens = []
    current = ""
    in_quotes = False
    for char in sql:
        if char == "'" or char == '"':
            in_quotes = not in_quotes
            current += char
        elif char == ' ' and not in_quotes:
            if current:
                tokens.append(current)
            current = ""
        else:
            current += char
    if current:
        tokens.append(current)
    return tokens

def compute_similarity(str1: str, str2: str) -> float:
    words1 = set(str1.lower().split())
    words2 = set(str2.lower().split())
    if not words1 or not words2:
        return 0.0
    overlap = len(words1 & words2) / max(len(words1), len(words2))
    sequence = SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
    return 0.7 * sequence + 0.3 * overlap

def find_best_matching_question(user_question: str, gold_questions: List[str]) -> Tuple[str, float]:
    similarities = [(q, compute_similarity(user_question, q)) for q in gold_questions]
    best_match, similarity = max(similarities, key=lambda x: x[1])
    if similarity < 0.3:
        user_terms = set(user_question.lower().split())
        for q in gold_questions:
            gold_terms = set(q.lower().split())
            if user_terms & gold_terms:
                return q, 0.3
    return best_match, similarity

def exact_match(pred: str, gold: str) -> bool:
    return normalize_sql(pred) == normalize_sql(gold)

def compute_prf(pred: str, gold: str) -> Tuple[float, float, float]:
    pred_tokens = set(tokenize_sql(normalize_sql(pred)))
    gold_tokens = set(tokenize_sql(normalize_sql(gold)))
    if not pred_tokens or not gold_tokens:
        return 0.0, 0.0, 0.0
    tp = len(pred_tokens & gold_tokens)
    precision = tp / len(pred_tokens)
    recall = tp / len(gold_tokens)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0
    return precision, recall, f1

def is_select_query(query: str) -> bool:
    return query.strip().lower().startswith("select")

def run_readonly_query(query: str) -> pd.DataFrame:
    if not is_select_query(query):
        return pd.DataFrame()
    try:
        return pd.read_sql(text(query), engine)
    except Exception as e:
        print(f"[Error executing query]: {e}")
        return pd.DataFrame()

def compare_results_semantically(pred_query: str, gold_query: str) -> bool:
    df_pred = run_readonly_query(pred_query)
    df_gold = run_readonly_query(gold_query)
    if df_pred.empty or df_gold.empty:
        return False
    try:
        if set(df_pred.columns) != set(df_gold.columns):
            return False
        df_pred = df_pred.sort_values(by=df_pred.columns.tolist()).reset_index(drop=True)
        df_gold = df_gold.sort_values(by=df_gold.columns.tolist()).reset_index(drop=True)
        for col in df_pred.columns:
            if df_pred[col].dtype != df_gold[col].dtype:
                return False
        return df_pred.equals(df_gold)
    except:
        return False

def validate_query(query: str) -> Tuple[bool, str]:
    if not query.strip():
        return False, "Empty query"
    if not is_select_query(query):
        return False, "Only SELECT queries are allowed"
    try:
        pd.read_sql(text(query), engine)
        return True, "Valid query"
    except Exception as e:
        return False, f"Invalid query: {str(e)}"

def evaluate(logs: List[Dict], gold_queries: Dict[str, str], similarity_threshold: float = 0.5) -> Dict:
    total = 0
    em_count = 0
    semantic_match_count = 0
    precisions, recalls, f1s = [], [], []
    mismatches = []
    gold_questions = list(gold_queries.keys())
    question_types = defaultdict(lambda: {"total": 0, "exact": 0, "semantic": 0})
    evaluation_results = {
        "total_questions": 0,
        "exact_matches": 0,
        "semantic_matches": 0,
        "avg_precision": 0.0,
        "avg_recall": 0.0,
        "avg_f1": 0.0,
        "mismatches": [],
        "invalid_queries": [],
        "question_type_performance": {},
        "similarity_distribution": []
    }
    for log in logs:
        question = log["question"].strip().lower()
        pred_sql = log["sql_query"]
        best_match, similarity = find_best_matching_question(question, gold_questions)
        evaluation_results["similarity_distribution"].append(similarity)
        if similarity < similarity_threshold:
            print(f"[Skipped] No sufficiently similar gold question found for: {question}")
            continue
        gold_sql = gold_queries[best_match]
        is_valid, validation_msg = validate_query(pred_sql)
        if not is_valid:
            evaluation_results["invalid_queries"].append({
                "question": question,
                "query": pred_sql,
                "error": validation_msg
            })
            continue
        total += 1
        evaluation_results["total_questions"] = total
        question_type = "simple"
        if "JOIN" in gold_sql.upper():
            question_type = "join"
        elif "GROUP BY" in gold_sql.upper():
            question_type = "aggregation"
        elif "WHERE" in gold_sql.upper():
            question_type = "filter"
        question_types[question_type]["total"] += 1
        if exact_match(pred_sql, gold_sql):
            em_count += 1
            evaluation_results["exact_matches"] = em_count
            question_types[question_type]["exact"] += 1
        else:
            mismatches.append({
                "question": question,
                "best_match": best_match,
                "similarity": similarity,
                "predicted": pred_sql,
                "gold": gold_sql,
                "type": question_type
            })
        p, r, f1 = compute_prf(pred_sql, gold_sql)
        precisions.append(p)
        recalls.append(r)
        f1s.append(f1)
        if compare_results_semantically(pred_sql, gold_sql):
            semantic_match_count += 1
            evaluation_results["semantic_matches"] = semantic_match_count
            question_types[question_type]["semantic"] += 1
    if total > 0:
        evaluation_results["avg_precision"] = np.mean(precisions)
        evaluation_results["avg_recall"] = np.mean(recalls)
        evaluation_results["avg_f1"] = np.mean(f1s)
        evaluation_results["mismatches"] = mismatches
        evaluation_results["question_type_performance"] = {
            qtype: {
                "total": stats["total"],
                "exact_match_rate": stats["exact"] / stats["total"] if stats["total"] > 0 else 0,
                "semantic_match_rate": stats["semantic"] / stats["total"] if stats["total"] > 0 else 0
            }
            for qtype, stats in question_types.items()
        }
        evaluation_results["similarity_distribution"] = {
            "mean": np.mean(evaluation_results["similarity_distribution"]),
            "median": np.median(evaluation_results["similarity_distribution"]),
            "min": np.min(evaluation_results["similarity_distribution"]),
            "max": np.max(evaluation_results["similarity_distribution"])
        }
    return evaluation_results

def print_evaluation_report(results: Dict):
    print("\n--- Evaluation Report ---")
    print(f"Total Questions Evaluated: {results['total_questions']}")
    print(f"Exact Matches: {results['exact_matches']} ({(results['exact_matches']/results['total_questions'])*100:.2f}%)")
    print(f"Semantic Matches: {results['semantic_matches']} ({(results['semantic_matches']/results['total_questions'])*100:.2f}%)")
    print(f"Average Precision: {results['avg_precision']:.3f}")
    print(f"Average Recall: {results['avg_recall']:.3f}")
    print(f"Average F1 Score: {results['avg_f1']:.3f}")
    print("\n--- Question Type Performance ---")
    for qtype, stats in results['question_type_performance'].items():
        print(f"\n{qtype.title()} Questions:")
        print(f"  Total: {stats['total']}")
        print(f"  Exact Match Rate: {stats['exact_match_rate']*100:.2f}%")
        print(f"  Semantic Match Rate: {stats['semantic_match_rate']*100:.2f}%")
    print("\n--- Similarity Distribution ---")
    sim_stats = results['similarity_distribution']
    print(f"Mean Similarity: {sim_stats['mean']:.3f}")
    print(f"Median Similarity: {sim_stats['median']:.3f}")
    print(f"Min Similarity: {sim_stats['min']:.3f}")
    print(f"Max Similarity: {sim_stats['max']:.3f}")
    if results['invalid_queries']:
        print("\n--- Invalid Queries ---")
        for invalid in results['invalid_queries']:
            print(f"Question: {invalid['question']}")
            print(f"Query: {invalid['query']}")
            print(f"Error: {invalid['error']}\n")
    if results['mismatches']:
        print("\n--- Mismatches ---")
        for m in results['mismatches']:
            print(f"Question: {m['question']}")
            print(f"Best Match: {m['best_match']} (similarity: {m['similarity']:.2f})")
            print(f"Type: {m['type']}")
            print(f"Predicted: {m['predicted']}")
            print(f"Gold: {m['gold']}\n")

if __name__ == "__main__":
    with open('gold_queries.json', 'r') as f:
        gold_queries = json.load(f)
    test_logs = []
    with open('sql_log.json', 'r') as f:
        for line in f:
            if line.strip():
                test_logs.append(json.loads(line))
    results = evaluate(test_logs, gold_queries)
    print_evaluation_report(results)
