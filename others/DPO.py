from datasets import Dataset

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
from peft import LoraConfig
from trl import DPOTrainer



# A toy dataset mimicking your ADE rewriting task
data = {
    "prompt": [
        "Rewrite the patient mention into a standard medical term. Mention: 'panic attacks'",
        "Rewrite the patient mention into a standard medical term. Mention: 'joint stiffness'"
    ],
    "chosen": [
        "Panic attack",      # Keeps the specific episode (Good for SapBERT)
        "Joint stiffness"    # Accurate mapping
    ],
    "rejected": [
        "Anxiety",           # Too broad / Granularity drift (Bad for SapBERT)
        "Arthralgia"         # Type shift / Inaccurate mapping
    ]
}

dataset = Dataset.from_dict(data)



model_id = "meta-llama/Meta-Llama-3-8B-Instruct"

# 1. Load the Tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_id)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

# 2. Load the Base Model (in 16-bit precision to save memory)
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    torch_dtype=torch.float16,
    device_map="auto"
)

# 3. Configure LoRA
# This tells the model: "Freeze the main weights, and only train small adapter matrices"
peft_config = LoraConfig(
    r=16,                                   # Rank of the adapter (controls parameter count)
    lora_alpha=32,                          # Scaling factor
    target_modules=["q_proj", "v_proj"],    # Which attention layers to target
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM"
)

# 4. Set up Training Arguments
training_args = TrainingArguments(
    output_dir="./dpo_llama3_ade",
    per_device_train_batch_size=2,
    learning_rate=5e-5,
    gradient_accumulation_steps=4,
    num_train_epochs=1,
    optim="paged_adamw_32bit",              # Memory efficient optimizer
    logging_steps=10
)

# 5. Initialize the DPO Trainer
# MAGIC TRICK HERE: By passing the peft_config, DPOTrainer automatically 
# uses the frozen base model as the "Reference Model" and trains only the LoRA adapters.
dpo_trainer = DPOTrainer(
    model=model,
    ref_model=None,                         # Set to None because PEFT handles it!
    args=training_args,
    beta=0.1,                               # KL penalty controls how far we can stray from the base model
    train_dataset=dataset,
    tokenizer=tokenizer,
    peft_config=peft_config,
    max_prompt_length=128,
    max_length=256
)

# 6. Start Training
dpo_trainer.train()

# 7. Save the trained LoRA adapter
dpo_trainer.model.save_pretrained("./final_dpo_adapter")