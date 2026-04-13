import json
from pathlib import Path
from collections import Counter

# 读取前1000个任务
jobs = []
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = PROJECT_ROOT / 'training' / 'data' / 'training_jobs_full.jsonl'

with open(DATA_FILE, encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i >= 1000:
            break
        if line.strip():
            jobs.append(json.loads(line))

print(f'读取任务数: {len(jobs)}')

# 分析文件名唯一性
file_keys = []
for job in jobs:
    # MVP版格式
    if "job_function" in job:
        profession = job["job_function"]
        scene_id = job["meta"]["scenario_id"]
        bucket = job["meta"]["bucket"]
    else:
        # FULL版格式
        profession = job.get("profession", "未知")
        scene_id = job.get("scenario_id", "未知")
        bucket = job["word_count"]
    
    profession_safe = profession.replace("/", "_").replace("\\", "_")
    scene_id_safe = scene_id.replace("/", "_").replace("\\", "_")
    language = job["language"]
    people = job["people_count"]
    seed = job["seed"]
    
    file_key = f"{profession_safe}/{language}/{scene_id_safe}_{bucket}_{people}_{seed}"
    file_keys.append(file_key)

# 统计唯一文件名
unique_keys = set(file_keys)
print(f'\n唯一文件名数: {len(unique_keys)}')
print(f'重复文件名数: {len(file_keys) - len(unique_keys)}')

# 找出重复的
counter = Counter(file_keys)
duplicates = [(k, v) for k, v in counter.items() if v > 1]
if duplicates:
    print(f'\n重复的文件（前10个）:')
    for key, count in duplicates[:10]:
        print(f'  {key}: {count}次')
else:
    print('\n没有重复文件')

# 按语言统计唯一文件数
lang_counter = Counter()
for key in unique_keys:
    lang = key.split('/')[1]
    lang_counter[lang] += 1

print('\n按语言统计唯一文件数:')
for lang, count in sorted(lang_counter.items()):
    print(f'  {lang}: {count}个')

