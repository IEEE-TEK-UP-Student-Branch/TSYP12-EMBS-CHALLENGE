import cv2
import numpy as np
from deepface import DeepFace
import speech_recognition as sr
import threading
import time
from collections import Counter
import queue
import torch
import tensorflow as tf

class EmotionSpeechAnalyzer:
    def __init__(self):
        self.video_capture = cv2.VideoCapture(0)
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Initialize GPU settings
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        if self.device.type == 'cuda':
            print(f"Using GPU: {torch.cuda.get_device_name(0)}")
        else:
            print("GPU not available, using CPU")
            
        # Configure TensorFlow to use GPU
        gpus = tf.config.list_physical_devices('GPU')
        if gpus:
            try:
                for gpu in gpus:
                    tf.config.experimental.set_memory_growth(gpu, True)
                print(f"TensorFlow GPU configuration successful")
            except RuntimeError as e:
                print(f"TensorFlow GPU configuration failed: {e}")
        
        # Check OpenCV CUDA support
        self.has_cuda = hasattr(cv2, 'cuda') and cv2.cuda.getCudaEnabledDeviceCount() > 0
        if self.has_cuda:
            print("OpenCV CUDA support available")
        else:
            print("OpenCV CUDA support not available, using CPU")
        
        # Queues for thread communication
        self.speech_queue = queue.Queue()
        self.emotion_queue = queue.Queue()
        
        # Storage for analysis
        self.full_text = []
        self.emotions = []
        self.is_running = True
        
        # Batch processing settings
        self.batch_size = 4 if self.device.type == 'cuda' else 1
        self.frame_buffer = []

    def detect_emotion(self, frames):
        try:
            # Process multiple frames in parallel if using GPU
            if isinstance(frames, list):
                analyses = DeepFace.analyze(frames, 
                                         actions=['emotion'], 
                                         enforce_detection=False,
                                         detector_backend='opencv',
                                         prog_bar=False)
                return [analysis['emotion'] for analysis in analyses]
            else:
                analysis = DeepFace.analyze(frames, 
                                          actions=['emotion'], 
                                          enforce_detection=False,
                                          detector_backend='opencv',
                                          prog_bar=False)
                return [analysis[0]['emotion']]
        except Exception as e:
            print(f"Emotion detection error: {e}")
            return None

    def process_video(self):
        while self.is_running:
            ret, frame = self.video_capture.read()
            if not ret:
                continue

            # Add frame to buffer
            self.frame_buffer.append(frame)
            
            # Process batch when buffer is full
            if len(self.frame_buffer) >= self.batch_size:
                emotions_batch = self.detect_emotion(self.frame_buffer)
                if emotions_batch:
                    for emotions in emotions_batch:
                        self.emotion_queue.put(emotions)
                self.frame_buffer = []

            # Process frame for display
            display_frame = frame.copy()
            if self.has_cuda:
                try:
                    # Use CUDA-accelerated image processing if available
                    cuda_frame = cv2.cuda_GpuMat()
                    cuda_frame.upload(display_frame)
                    cuda_frame = cv2.cuda.resize(cuda_frame, (640, 480))
                    display_frame = cuda_frame.download()
                except cv2.error as e:
                    print(f"CUDA processing error, falling back to CPU: {e}")
                    display_frame = cv2.resize(display_frame, (640, 480))
            else:
                # Use CPU processing
                display_frame = cv2.resize(display_frame, (640, 480))
            
            cv2.imshow('Video Feed (Press Q to stop)', display_frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.is_running = False

    def record_audio(self):
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source)
            
            while self.is_running:
                try:
                    audio = self.recognizer.listen(source, timeout=5)
                    text = self.recognizer.recognize_google(audio)
                    self.speech_queue.put(text)
                except sr.WaitTimeoutError:
                    continue
                except sr.UnknownValueError:
                    continue
                except sr.RequestError:
                    print("Could not request results from speech recognition service")

    def analyze_emotions(self):
        emotion_counts = Counter()
        total_readings = 0
        
        while not self.emotion_queue.empty():
            emotions = self.emotion_queue.get()
            max_emotion = max(emotions.items(), key=lambda x: x[1])[0]
            emotion_counts[max_emotion] += 1
            total_readings += 1
        
        # Calculate percentages using GPU if available
        if total_readings > 0:
            if self.device.type == 'cuda':
                # Convert to PyTorch tensors for GPU acceleration
                counts = torch.tensor(list(emotion_counts.values()), device=self.device).float()
                percentages = (counts / total_readings) * 100
                percentages = percentages.cpu().numpy()
                emotion_percentages = dict(zip(emotion_counts.keys(), percentages))
            else:
                emotion_percentages = {
                    emotion: (count/total_readings) * 100 
                    for emotion, count in emotion_counts.most_common()
                }
            return emotion_percentages
        return {}

    def run(self):
        # Start threads for video and audio processing
        video_thread = threading.Thread(target=self.process_video)
        audio_thread = threading.Thread(target=self.record_audio)
        
        video_thread.start()
        audio_thread.start()
        
        # Process until stopped
        while self.is_running:
            while not self.speech_queue.empty():
                text = self.speech_queue.get()
                self.full_text.append(text)
            time.sleep(0.1)
        
        # Clean up
        video_thread.join()
        audio_thread.join()
        self.video_capture.release()
        cv2.destroyAllWindows()
        
        # Generate final output
        final_text = " ".join(self.full_text)
        emotion_percentages = self.analyze_emotions()
        
        # Format output
        output = f"STT: {final_text}\nEmotion:"
        for emotion, percentage in emotion_percentages.items():
            output += f"\n{emotion}: {percentage:.1f}%"
        
        return output

def main():
    analyzer = EmotionSpeechAnalyzer()
    result = analyzer.run()
    print("\nFinal Analysis:")
    print(result)

if __name__ == "__main__":
    main()