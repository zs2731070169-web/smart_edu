# windows
python "G:\project\smart_edu\uie_pytorch\evaluate.py" ^
--model_path "G:\project\smart_edu\checkpoint\model_best" ^
--test_path "G:\project\smart_edu\data\processed\test.txt" ^
--batch_size 16 ^
--max_seq_len 512

# linux
python "/Users/baitiaojun/python_projects/smart_edu/uie_pytorch/evaluate.py" \
--model_path "/Users/baitiaojun/python_projects/smart_edu/checkpoint/model_best" \
--test_path "/Users/baitiaojun/python_projects/smart_edu/data/processed/test.txt" \
--batch_size 16 \
--max_seq_len 512 \
--device "cpu"