# windows
python "G:\project\smart_edu\uie_pytorch\finetune.py" ^
--train_path "G:\project\smart_edu\data\processed\train.txt" ^
--dev_path "G:\project\smart_edu\data\processed\dev.txt" ^
--save_dir "G:\project\smart_edu\checkpoint" ^
--learning_rate 3e-5 ^
--batch_size 4 ^
--max_seq_len 512 ^
--num_epochs 20 ^
--model "G:\project\smart_edu\models\uie_base_pytorch" ^
--logging_steps 2 ^
--valid_steps 10 ^
--device "gpu" ^
--max_model_num 3

# linux
python /Users/baitiaojun/python_projects/smart_edu/uie_pytorch/finetune.py \
--train_path "/Users/baitiaojun/python_projects/smart_edu/data/processed/train.txt" \
--dev_path "/Users/baitiaojun/python_projects/smart_edu/data/processed/dev.txt" \
--save_dir "/Users/baitiaojun/python_projects/smart_edu/checkpoint" \
--learning_rate 3e-5 \
--batch_size 4 \
--max_seq_len 512 \
--num_epochs 20 \
--model "/Users/baitiaojun/python_projects/smart_edu/models/uie_base_pytorch" \
--logging_steps 2 \
--valid_steps 10 \
--device "gpu" \
—max_model_num 3