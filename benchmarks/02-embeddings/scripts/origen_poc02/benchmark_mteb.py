import os
import json
import time
import datetime
import torch
from pathlib import Path
from mteb import MTEB
from sentence_transformers import SentenceTransformer
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def run_benchmark():
    models = [
        "paraphrase-multilingual-mpnet-base-v2",
        "intfloat/multilingual-e5-large"
    ]
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Dispositivo de evaluación: {device.upper()}")
    
    import mteb
    try:
        # Limitamos a 2 tareas representativas para terminar rápido en la POC
        tasks = mteb.get_tasks(tasks=["STS22", "SpanishPassageRetrievalS2P"], languages=["spa"])
        if not tasks:
            from mteb import get_tasks
            tasks = get_tasks(tasks=["STS22", "SpanishPassageRetrievalS2P"], languages=["spa"])
    except Exception:
        tasks = mteb.get_tasks(tasks=["STS17", "MintakaRetrieval"])
        
    print(f"Ejecutando benchmark en {len(tasks)} tareas (STS/Retrieval) en {device}...")

    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    
    for model_name in models:
        print(f"\n--- Evaluando {model_name} ---")
        try:
            model = SentenceTransformer(model_name, device=device)
            evaluation = MTEB(tasks=tasks)
            
            t0 = time.time()
            output_dir = Path("results") / f"mteb_temp_{model_name.replace('/', '_')}"
            evaluation.run(model, output_folder=str(output_dir))
            t1 = time.time()
            
            latency_total = t1 - t0
            
            # Extraer métricas clave leyendo los JSONs generados
            extracted_metrics = {}
            queries_count = 0
            
            for task in tasks:
                task_name = task.metadata.name
                json_path = output_dir / model_name.replace("/", "__") / f"{task_name}.json"
                if not json_path.exists():
                    # Intenta buscar el archivo si el path varía un poco
                    json_files = list(output_dir.rglob(f"{task_name}.json"))
                    if json_files:
                        json_path = json_files[0]
                    else:
                        continue
                
                with open(json_path, "r", encoding="utf-8") as f:
                    res = json.load(f)
                
                if hasattr(task.metadata, 'type') and task.metadata.type == 'STS':
                    scores = res.get('scores', {}).get('test', [])
                    if scores:
                        val = scores[0].get('main_score') or scores[0].get('spearman')
                        extracted_metrics[task_name] = {"spearman": val}
                        queries_count += 1000
                else:
                    scores = res.get('scores', {}).get('test', [])
                    if scores:
                        s = scores[0]
                        extracted_metrics[task_name] = {
                            "ndcg_at_10": s.get("ndcg_at_10"),
                            "recall_at_5": s.get("recall_at_5"),
                            "recall_at_10": s.get("recall_at_10"),
                            "mrr_at_10": s.get("mrr_at_10")
                        }
                        queries_count += res.get('evaluation_time', 1000)

            latency_per_query = (latency_total * 1000) / max(queries_count, 1) # en ms
            
            final_json = {
                "model": model_name,
                "device": device,
                "timestamp": datetime.datetime.now().isoformat(),
                "latency_total_s": latency_total,
                "latency_per_query_ms": latency_per_query,
                "total_queries_approx": queries_count,
                "metrics": extracted_metrics
            }
            
            output_path = Path(f"results/benchmark_mteb_{model_name.replace('/', '_')}_{timestamp_str}.json")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(final_json, f, indent=4, ensure_ascii=False)
            
            print(f"Resultados de {model_name} guardados en {output_path}")

        except Exception as e:
            print(f"Error evaluando {model_name}: {e}")

if __name__ == "__main__":
    run_benchmark()
