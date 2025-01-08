from transformers import T5Tokenizer, T5ForConditionalGeneration
from torch.utils.data import DataLoader, Dataset
import torch

# Custom Dataset
class SquadDataset(Dataset):
    def __init__(self, data, tokenizer, max_length=512):
        self.data = data
        self.tokenizer = tokenizer
        self.max_length = max_length
    
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        entry = self.data[idx]
        question = entry['question']
        context = entry['context']
        answers = entry['answers']['text'][0]  # Lấy câu trả lời đầu tiên
        
        inputs = f"question: {question} context: {context} </s>"
        targets = f"answer: {answers} </s>"
        
        encoding = self.tokenizer(inputs, max_length=self.max_length, padding="max_length", truncation=True, return_tensors="pt")
        target_encoding = self.tokenizer(targets, max_length=self.max_length, padding="max_length", truncation=True, return_tensors="pt")
        
        return {
            'input_ids': encoding['input_ids'].squeeze(0),
            'attention_mask': encoding['attention_mask'].squeeze(0),
            'labels': target_encoding['input_ids'].squeeze(0)
        }

# Load dataset from Hugging Face SQuAD
from datasets import load_dataset

dataset = load_dataset("squad")

# Load tokenizer and model
tokenizer = T5Tokenizer.from_pretrained("t5-small")
model = T5ForConditionalGeneration.from_pretrained("t5-small")

# Create dataset and dataloader
train_dataset = SquadDataset(dataset["train"], tokenizer)
train_loader = DataLoader(train_dataset, batch_size=8, shuffle=True)

# Train function
def train_model(model, dataloader, optimizer, epochs=3, device='cuda' if torch.cuda.is_available() else 'cpu'):
    model.train()
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=5e-5)
    
    for epoch in range(epochs):
        total_loss = 0
        for batch in dataloader:
            inputs = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['labels'].to(device)
            
            outputs = model(input_ids=inputs, attention_mask=attention_mask, labels=labels)
            loss = outputs.loss
            total_loss += loss.item()
            
            loss.backward()
            optimizer.step()
            optimizer.zero_grad()
        
        print(f"Epoch {epoch+1}/{epochs}, Loss: {total_loss / len(dataloader)}")

    model.save_pretrained("./t5_model")
    tokenizer.save_pretrained("./t5_model")


# Train the model
optimizer = torch.optim.AdamW(model.parameters(), lr=5e-5)    
train_model(model, train_loader,optimizer, epochs=3)
