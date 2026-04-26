# ML Rules

- All experiments tracked in MLflow — always use `mlflow.start_run()`
- Features defined in `features.py` — never inline feature engineering in train.py
- Model registered as `pathfinder-appeal-scorer` in MLflow registry
- Train/val/test split: 70/15/15, stratified by county
- Minimum 50 training records required before training
- SHAP values computed per prediction in `scoring_service.py`
