from transformers import AutoModelForSemanticSegmentation
model = AutoModelForSemanticSegmentation.from_pretrained('mattmdjaga/segformer_b2_clothes')
print(model.config.id2label)
