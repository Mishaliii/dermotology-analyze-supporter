from transformers import SegformerImageProcessor, AutoModelForSemanticSegmentation

model_id = "matei-dorian/segformer-b0-finetuned-human-parsing"
try:
    processor = SegformerImageProcessor.from_pretrained(model_id)
    model = AutoModelForSemanticSegmentation.from_pretrained(model_id)
    print("Labels for:", model_id)
    print(model.config.id2label)
except Exception as e:
    print(f"Error loading {model_id}: {e}")

model_id = "mattmdjaga/segformer_b2_clothes"
try:
    processor = SegformerImageProcessor.from_pretrained(model_id)
    model = AutoModelForSemanticSegmentation.from_pretrained(model_id)
    print("Labels for:", model_id)
    print(model.config.id2label)
except Exception as e:
    print(f"Error loading {model_id}: {e}")
