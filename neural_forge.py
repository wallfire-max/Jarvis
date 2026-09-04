import os
import json
import random
import time
import threading
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.svm import SVC, SVR
from sklearn.metrics import accuracy_score, r2_score, mean_squared_error, confusion_matrix, classification_report
import matplotlib
matplotlib.use('Agg') # Thread-safe backend for rendering plots without UI
import matplotlib.pyplot as plt

# Directories
STATIC_DIR = "C:\\Users\\Jaswa\\OneDrive\\Desktop\\rudra\\static"
PLOTS_DIR = os.path.join(STATIC_DIR, "img", "ml_plots")
MODELS_DIR = "C:\\Users\\Jaswa\\OneDrive\\Desktop\\rudra\\models"

os.makedirs(PLOTS_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

# ────────────────────────────────────────────────────────
#  PART 1 — PURE NUMPY CHARACTER-LEVEL LANGUAGE MODEL (RNN)
# ────────────────────────────────────────────────────────

class CharRNN:
    """Vanilla recurrent neural network written in pure NumPy."""
    def __init__(self, vocab_size, hidden_size=100, seq_length=25, lr=0.1):
        self.vocab_size = vocab_size
        self.hidden_size = hidden_size
        self.seq_length = seq_length
        self.lr = lr

        # Model parameters
        # Input to hidden
        self.Wxh = np.random.randn(hidden_size, vocab_size) * 0.01
        # Hidden to hidden
        self.Whh = np.random.randn(hidden_size, hidden_size) * 0.01
        # Hidden to output
        self.Why = np.random.randn(vocab_size, hidden_size) * 0.01
        # Hidden bias
        self.bh = np.zeros((hidden_size, 1))
        # Output bias
        self.by = np.zeros((vocab_size, 1))

        # AdaGrad memory variables for parameter updates
        self.mWxh = np.zeros_like(self.Wxh)
        self.mWhh = np.zeros_like(self.Whh)
        self.mWhy = np.zeros_like(self.Why)
        self.mbh = np.zeros_like(self.bh)
        self.mby = np.zeros_like(self.by)

    def lossFun(self, inputs, targets, hprev):
        """
        inputs, targets are lists of integers.
        hprev is Hx1 array of initial hidden state.
        returns the loss, gradients on model parameters, and last hidden state
        """
        xs, hs, ys, ps = {}, {}, {}, {}
        hs[-1] = np.copy(hprev)
        loss = 0
        
        # ── Forward pass ───────────────────
        for t in range(len(inputs)):
            # Encoding input in 1-of-k representation
            xs[t] = np.zeros((self.vocab_size, 1))
            xs[t][inputs[t]] = 1
            
            # Update hidden state
            hs[t] = np.tanh(np.dot(self.Wxh, xs[t]) + np.dot(self.Whh, hs[t-1]) + self.bh)
            
            # Unnormalized log probabilities for next chars
            ys[t] = np.dot(self.Why, hs[t]) + self.by
            
            # Probabilities for next chars
            ps[t] = np.exp(ys[t]) / np.sum(np.exp(ys[t]))
            
            # Softmax cross-entropy loss
            loss += -np.log(ps[t][targets[t], 0])

        # Gradients
        dWxh, dWhh, dWhy = np.zeros_like(self.Wxh), np.zeros_like(self.Whh), np.zeros_like(self.Why)
        dbh, dby = np.zeros_like(self.bh), np.zeros_like(self.by)
        dhnext = np.zeros_like(hs[0])

        # ── Backward pass ──────────────────
        for t in reversed(range(len(inputs))):
            dy = np.copy(ps[t])
            # Backprop into softmax
            dy[targets[t]] -= 1
            
            dWhy += np.dot(dy, hs[t].T)
            dby += dy
            
            dh = np.dot(self.Why.T, dy) + dhnext # Backprop into hidden state
            dhraw = (1 - hs[t] * hs[t]) * dh    # Backprop through tanh nonlinearity
            
            dbh += dhraw
            dWxh += np.dot(dhraw, xs[t].T)
            dWhh += np.dot(dhraw, hs[t-1].T)
            
            dhnext = np.dot(self.Whh.T, dhraw)

        # Clip gradients to prevent exploding gradients
        for dparam in [dWxh, dWhh, dWhy, dbh, dby]:
            np.clip(dparam, -5, 5, out=dparam)

        return loss, dWxh, dWhh, dWhy, dbh, dby, hs[len(inputs)-1]

    def sample(self, h, seed_ix, n, temp=0.8):
        """
        Sample a sequence of integers from the model
        h is memory state, seed_ix is seed letter for first time step
        temp is temperature (higher temp = more creative/random)
        """
        x = np.zeros((self.vocab_size, 1))
        x[seed_ix] = 1
        ixes = []
        for t in range(n):
            h = np.tanh(np.dot(self.Wxh, x) + np.dot(self.Whh, h) + self.bh)
            y = np.dot(self.Why, h) + self.by
            
            # Apply temperature scaling to log probabilities
            y_scaled = y / max(0.1, temp)
            p = np.exp(y_scaled) / np.sum(np.exp(y_scaled))
            
            ix = np.random.choice(range(self.vocab_size), p=p.ravel())
            x = np.zeros((self.vocab_size, 1))
            x[ix] = 1
            ixes.append(ix)
        return ixes

    def update_parameters(self, dWxh, dWhh, dWhy, dbh, dby):
        """Perform AdaGrad parameter update step."""
        for param, dparam, mem in zip(
            [self.Wxh, self.Whh, self.Why, self.bh, self.by],
            [dWxh, dWhh, dWhy, dbh, dby],
            [self.mWxh, self.mWhh, self.mWhy, self.mbh, self.mby]
        ):
            mem += dparam * dparam
            param += -self.lr * dparam / np.sqrt(mem + 1e-8)


class CharRNNTrainer:
    """Manager class to load text files and run the Char-RNN training loop in a thread."""
    def __init__(self):
        self.is_training = False
        self.stop_signal = False
        self.model = None
        self.vocab = []
        self.char_to_ix = {}
        self.ix_to_char = {}

    def start_training(self, text_corpus, epochs=500, hidden_size=128, seq_length=30, lr=0.08, on_progress_callback=None):
        if self.is_training:
            return False
            
        self.stop_signal = False
        self.is_training = True
        
        # Prepare vocabulary mapping
        self.vocab = sorted(list(set(text_corpus)))
        vocab_size = len(self.vocab)
        self.char_to_ix = {ch: i for i, ch in enumerate(self.vocab)}
        self.ix_to_char = {i: ch for i, ch in enumerate(self.vocab)}
        
        # Initialize model
        self.model = CharRNN(vocab_size, hidden_size=hidden_size, seq_length=seq_length, lr=lr)
        
        # Launch thread
        t = threading.Thread(
            target=self._training_loop,
            args=(text_corpus, epochs, on_progress_callback),
            daemon=True
        )
        t.start()
        return True

    def stop_training(self):
        if self.is_training:
            self.stop_signal = True

    def _training_loop(self, data, epochs, on_progress_callback):
        n, p = 0, 0
        hprev = np.zeros((self.model.hidden_size, 1))
        smooth_loss = -np.log(1.0 / self.model.vocab_size) * self.model.seq_length # initial rough loss
        
        epoch_count = 0
        
        while epoch_count < epochs and not self.stop_signal:
            # Prepare inputs (we sweep through the text data)
            if p + self.model.seq_length + 1 >= len(data) or n == 0:
                hprev = np.zeros((self.model.hidden_size, 1)) # reset RNN memory state
                p = 0 # go back to start of data
                
            inputs = [self.char_to_ix[ch] for ch in data[p:p + self.model.seq_length]]
            targets = [self.char_to_ix[ch] for ch in data[p+1:p + self.model.seq_length + 1]]
            
            # Forward + Backward
            loss, dWxh, dWhh, dWhy, dbh, dby, hprev = self.model.lossFun(inputs, targets, hprev)
            self.model.update_parameters(dWxh, dWhh, dWhy, dbh, dby)
            smooth_loss = smooth_loss * 0.999 + loss * 0.001
            
            # Periodic evaluation & logging
            if n % 100 == 0:
                epoch_count += 1
                
                # Sample text from the model
                sample_ixes = self.model.sample(hprev, inputs[0], 150)
                sample_txt = ''.join(self.ix_to_char[ix] for ix in sample_ixes)
                
                print(f"Epoch {epoch_count}/{epochs} | Loss: {smooth_loss:.4f}")
                
                if on_progress_callback:
                    on_progress_callback({
                        "epoch": epoch_count,
                        "loss": round(smooth_loss, 4),
                        "sample": sample_txt,
                        "status": "training"
                    })
                    
            p += self.model.seq_length # move data pointer
            n += 1
            time.sleep(0.005) # slow down slightly to save CPU
            
        self.is_training = False
        
        if on_progress_callback:
            status_str = "aborted" if self.stop_signal else "completed"
            # Final sample
            final_ixes = self.model.sample(hprev, 0, 200)
            final_txt = ''.join(self.ix_to_char[ix] for ix in final_ixes)
            
            on_progress_callback({
                "epoch": epoch_count,
                "loss": round(smooth_loss, 4),
                "sample": final_txt,
                "status": status_str
            })

    def generate_completion(self, seed_text, count=200, temp=0.7):
        if not self.model:
            return "Error: No model trained yet Sir."
            
        h = np.zeros((self.model.hidden_size, 1))
        # Warm up the RNN hidden state using the seed text
        seed_ix = 0
        for ch in seed_text:
            if ch in self.char_to_ix:
                seed_ix = self.char_to_ix[ch]
                h = np.tanh(np.dot(self.model.Wxh, np.eye(self.model.vocab_size)[:, [seed_ix]]) + np.dot(self.model.Whh, h) + self.model.bh)
                
        # Generate characters
        ixes = self.model.sample(h, seed_ix, count, temp=temp)
        completion = seed_text + ''.join(self.ix_to_char[ix] for ix in ixes)
        return completion

# Create global tracker instance
gpt_trainer = CharRNNTrainer()


# ────────────────────────────────────────────────────────
#  PART 2 — TABULAR DATASET TRAINING (SCIKIT-LEARN)
# ────────────────────────────────────────────────────────

def preprocess_and_split(df, target_col):
    df_clean = df.copy()
    
    # Fill missing values
    for col in df_clean.columns:
        if df_clean[col].dtype in ['int64', 'float64']:
            df_clean[col] = df_clean[col].fillna(df_clean[col].median())
        else:
            df_clean[col] = df_clean[col].fillna(df_clean[col].mode().iloc[0] if not df_clean[col].mode().empty else "missing")
            
    # Label encode categorical columns
    le_dict = {}
    for col in df_clean.columns:
        if col != target_col and df_clean[col].dtype == 'object':
            le = LabelEncoder()
            df_clean[col] = le.fit_transform(df_clean[col].astype(str))
            le_dict[col] = le
            
    # Handle target encoding if categorical
    is_classification = df_clean[target_col].dtype == 'object' or len(df_clean[target_col].unique()) < 10
    if is_classification and df_clean[target_col].dtype == 'object':
        le_target = LabelEncoder()
        df_clean[target_col] = le_target.fit_transform(df_clean[target_col].astype(str))
        le_dict[target_col] = le_target
        
    X = df_clean.drop(columns=[target_col])
    y = df_clean[target_col]
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    return X_train, X_test, y_train, y_test, is_classification, le_dict

def train_tabular_model(csv_path, target_col, model_type='rf', hyperparams=None):
    if not os.path.exists(csv_path):
        return {"error": f"Dataset file '{os.path.basename(csv_path)}' not found."}
        
    df = pd.read_csv(csv_path)
    if target_col not in df.columns:
        return {"error": f"Target column '{target_col}' not found in dataset columns."}
        
    # Preprocess
    X_train, X_test, y_train, y_test, is_classification, encoders = preprocess_and_split(df, target_col)
    
    # Setup hyperparameters
    if hyperparams is None:
        hyperparams = {}
        
    # Model instantiation
    model_name = ""
    if is_classification:
        if model_type == 'rf':
            n_est = int(hyperparams.get("n_estimators", 100))
            model = RandomForestClassifier(n_estimators=n_est, random_state=42)
            model_name = f"Random Forest Classifier (Trees: {n_est})"
        elif model_type == 'dt':
            model = DecisionTreeClassifier(random_state=42)
            model_name = "Decision Tree Classifier"
        elif model_type == 'lr':
            model = LogisticRegression(max_iter=500, random_state=42)
            model_name = "Logistic Regression"
        else:
            model = SVC(kernel='rbf', probability=True)
            model_name = "Support Vector Machine Classifier (RBF)"
    else:
        if model_type == 'rf':
            n_est = int(hyperparams.get("n_estimators", 100))
            model = RandomForestRegressor(n_estimators=n_est, random_state=42)
            model_name = f"Random Forest Regressor (Trees: {n_est})"
        elif model_type == 'dt':
            model = DecisionTreeRegressor(random_state=42)
            model_name = "Decision Tree Regressor"
        elif model_type == 'lr':
            model = LinearRegression()
            model_name = "Linear Regression"
        else:
            model = SVR(kernel='rbf')
            model_name = "Support Vector Regressor"
            
    # Train
    start_time = time.time()
    model.fit(X_train, y_train)
    train_time = f"{time.time() - start_time:.4f}s"
    
    # Predict
    preds = model.predict(X_test)
    
    metrics = {
        "model_name": model_name,
        "is_classification": is_classification,
        "train_time": train_time,
        "features": list(X_train.columns)
    }
    
    # Calculate performance metrics
    if is_classification:
        acc = accuracy_score(y_test, preds)
        cm = confusion_matrix(y_test, preds)
        rep = classification_report(y_test, preds, output_dict=True)
        metrics["accuracy"] = f"{acc * 100:.2f}%"
        metrics["f1_score"] = f"{rep['macro avg']['f1-score']:.4f}"
        metrics["details"] = f"Accuracy: {acc:.4f} | F1: {rep['macro avg']['f1-score']:.4f}"
        
        # Save confusion matrix plot
        plt.figure(figsize=(5, 4))
        plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Oranges)
        plt.title('Confusion Matrix')
        plt.colorbar()
        plt.xlabel('Predicted label')
        plt.ylabel('True label')
        plt.tight_layout()
        plot_path = os.path.join(PLOTS_DIR, "latest_run.png")
        plt.savefig(plot_path, dpi=120, transparent=True)
        plt.close()
    else:
        r2 = r2_score(y_test, preds)
        mse = mean_squared_error(y_test, preds)
        metrics["r2_score"] = f"{r2:.4f}"
        metrics["mse"] = f"{mse:.4f}"
        metrics["details"] = f"R² Score: {r2:.4f} | MSE: {mse:.4f}"
        
        # Save actual vs predicted plot
        plt.figure(figsize=(5, 4))
        plt.scatter(y_test, preds, color='#ff5500', alpha=0.6, edgecolors='k')
        plt.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], 'k--', lw=1.5, color='#ffffff')
        plt.title('Actual vs Predicted')
        plt.xlabel('Actual')
        plt.ylabel('Predicted')
        # Dark style labels
        plt.gca().set_facecolor('none')
        plt.gcf().patch.set_facecolor('none')
        plt.tight_layout()
        plot_path = os.path.join(PLOTS_DIR, "latest_run.png")
        plt.savefig(plot_path, dpi=120, transparent=True)
        plt.close()

    # Save model and columns for future prediction
    import joblib
    model_save_path = os.path.join(MODELS_DIR, "latest_model.joblib")
    meta_save_path = os.path.join(MODELS_DIR, "latest_model_meta.json")
    
    # Save model file
    joblib.dump(model, model_save_path)
    
    # Save column configuration
    with open(meta_save_path, 'w') as f:
        json.dump({
            "features": list(X_train.columns),
            "target": target_col,
            "is_classification": is_classification,
            "model_type": model_type
        }, f)
        
    return metrics

def query_tabular_model(inputs):
    """
    inputs is a dictionary matching training features.
    returns model prediction.
    """
    model_save_path = os.path.join(MODELS_DIR, "latest_model.joblib")
    meta_save_path = os.path.join(MODELS_DIR, "latest_model_meta.json")
    
    if not os.path.exists(model_save_path) or not os.path.exists(meta_save_path):
        return {"error": "No trained model found. Please train a model first!"}
        
    import joblib
    with open(meta_save_path, 'r') as f:
        meta = json.load(f)
        
    model = joblib.load(model_save_path)
    features = meta["features"]
    
    # Build dataframe row
    row_data = {}
    for f in features:
        val = inputs.get(f)
        if val is None:
            # Fallback
            row_data[f] = 0.0
        else:
            try:
                row_data[f] = float(val)
            except:
                row_data[f] = val
                
    df_row = pd.DataFrame([row_data])
    
    # Run prediction
    pred = model.predict(df_row)[0]
    
    return {
        "prediction": str(pred),
        "target": meta["target"],
        "is_classification": meta["is_classification"]
    }
