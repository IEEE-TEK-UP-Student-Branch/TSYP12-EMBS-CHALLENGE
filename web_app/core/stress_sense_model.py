import os
import tensorflow as tf
import pandas as pd
import numpy as np

class StressSenseModel:
    def __init__(self):
        self.model = None
        self.behavior_mapping = {
            0: "Eating",
            1: "Nail_Biting",
            2: "Face_Touch",
            3: "Smoking",
            4: "Staying_Still"
        }
        self.load_model()

    def load_model(self):
        """Load the trained stress sense model"""
        model_path = os.path.join(os.path.dirname(__file__), 'stress_sense_model.h5')
        self.model = tf.keras.models.load_model(model_path)

    def get_latest_biometric_data(self):
        """Get the latest row of biometric data without the label"""
        data_path = os.path.join(os.path.dirname(__file__), 'Biometric_data.csv')
        df = pd.read_csv(data_path)
        return df.iloc[-1:].drop('label', axis=1).values

    def predict_behavior(self):
        """
        Predict behavior based on latest biometric data
        Returns: String describing the predicted behavior
        """
        if self.model is None:
            self.load_model()

        # Get latest data
        latest_data = self.get_latest_biometric_data()
        
        # Make prediction
        prediction = self.model.predict(latest_data)
        behavior_index = np.argmax(prediction)
        
        return self.behavior_mapping[behavior_index]