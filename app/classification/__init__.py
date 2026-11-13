"""Classification: clean Reviews get Topics, sentiment and confidence from the fast model, in batches."""

from app.classification._classification import BATCH_SIZE, TASK, ClassificationResult, Classifier

__all__ = ["BATCH_SIZE", "TASK", "ClassificationResult", "Classifier"]
