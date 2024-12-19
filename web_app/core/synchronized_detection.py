import numpy as np
import cv2
from deepface import DeepFace
import time
import os
import tensorflow as tf
from moviepy.editor import VideoFileClip
import speech_recognition as sr
import tempfile
import wave

# Configure TensorFlow to use GPU
print("TensorFlow version:", tf.__version__)

# Set environment variables for GPU memory allocation
os.environ['TF_FORCE_GPU_ALLOW_GROWTH'] = 'true'
os.environ['TF_GPU_ALLOCATOR'] = 'cuda_malloc_async'

# Set memory growth
physical_devices = tf.config.list_physical_devices('GPU')
if physical_devices:
    try:
        for device in physical_devices:
            tf.config.experimental.set_memory_growth(device, True)
            print(f"Memory growth enabled on GPU device: {device}")
    except RuntimeError as e:
        print(f"GPU configuration error: {e}")
else:
    print("No GPU devices found. Using CPU.")

class MultimodalDetector:
    def __init__(self):
        # Initialize speech recognizer
        self.recognizer = sr.Recognizer()
        print("Speech recognition initialized!")

        # Processing parameters
        self.block_duration = 5  # seconds
        self.target_fps = 30  # Target FPS for video processing

    def process_video_frames(self, video_path, start_time, end_time):
        """Process video frames for a specific time block."""
        video = cv2.VideoCapture(video_path)
        if not video.isOpened():
            print("Error: Could not open video file")
            return None

        fps = video.get(cv2.CAP_PROP_FPS)
        frame_interval = max(1, round(fps / self.target_fps))
        
        start_frame = int(start_time * fps)
        end_frame = int(end_time * fps)
        
        # Calculate number of frames to process
        total_frames = end_frame - start_frame
        frames_to_process = total_frames // frame_interval
        
        print(f"Processing frames {start_frame} to {end_frame} (interval: {frame_interval})")
        print(f"Will process {frames_to_process} frames")
        
        emotions = []
        video.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        frames_processed = 0
        
        try:
            for _ in range(start_frame, end_frame, frame_interval):
                ret, frame = video.read()
                if not ret:
                    break
                
                # Skip frames according to interval
                for _ in range(frame_interval - 1):
                    video.read()
                
                try:
                    # Resize frame to make processing faster
                    frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
                    
                    emotion = DeepFace.analyze(
                        frame,
                        actions=['emotion'],
                        enforce_detection=False,
                        detector_backend='opencv',
                        silent=True
                    )
                    if emotion:
                        emotions.append(emotion[0]['emotion'])
                        frames_processed += 1
                        if frames_processed % 5 == 0:  # Print progress every 5 frames
                            print(f"Processed {frames_processed}/{frames_to_process} frames")
                except Exception as e:
                    print(f"Error in emotion detection for frame {start_frame + frames_processed * frame_interval}: {e}")
                    continue
                
        except Exception as e:
            print(f"Error processing video block: {e}")
        finally:
            video.release()

        print(f"Successfully processed {frames_processed} frames")

        # Calculate dominant emotion
        if emotions:
            dominant_emotion = {
                'angry': 0, 'disgust': 0, 'fear': 0,
                'happy': 0, 'sad': 0, 'surprise': 0, 'neutral': 0
            }
            for e in emotions:
                for emotion, score in e.items():
                    dominant_emotion[emotion] += score
            
            # Average the scores
            for emotion in dominant_emotion:
                if len(emotions) > 0:  # Avoid division by zero
                    dominant_emotion[emotion] /= len(emotions)
            
            # Get the emotion with highest score
            max_emotion = max(dominant_emotion.items(), key=lambda x: x[1])
            return {max_emotion[0]: max_emotion[1]}
        
        return {'neutral': 1.0}

    def process_audio_segment(self, audio_segment, start_time, end_time):
        """Process an audio segment using SpeechRecognition."""
        try:
            # Extract the audio segment
            segment = audio_segment.subclip(start_time, end_time)
            
            # Create a temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
                temp_path = temp_audio.name
                segment.write_audiofile(temp_path, codec='pcm_s16le', fps=16000)
            
            try:
                # Use speech recognition
                with sr.AudioFile(temp_path) as source:
                    # Adjust for ambient noise
                    self.recognizer.adjust_for_ambient_noise(source)
                    # Record audio from file
                    audio = self.recognizer.record(source)
                    # Perform recognition
                    text = self.recognizer.recognize_google(audio)
                    return text
            finally:
                # Clean up temporary file
                os.unlink(temp_path)
                
        except Exception as e:
            print(f"Error processing audio segment: {e}")
            return ""

    def process_video(self, video_path):
        """Process video and audio sequentially."""
        print(f"\nProcessing video file: {video_path}")
        
        # Check if input is webm and convert to mp4 if needed
        file_ext = os.path.splitext(video_path)[1].lower()
        if file_ext == '.webm':
            print("Converting webm to mp4...")
            output_path = os.path.splitext(video_path)[0] + '_converted.mp4'
            try:
                # Use ffmpeg to convert webm to mp4
                import subprocess
                command = [
                    'ffmpeg',
                    '-i', video_path,  # Input file
                    '-c:v', 'libx264',  # Video codec
                    '-c:a', 'aac',      # Audio codec
                    '-strict', 'experimental',
                    '-y',               # Overwrite output file if exists
                    output_path
                ]
                
                # Run the conversion
                result = subprocess.run(command, capture_output=True, text=True)
                
                if result.returncode != 0:
                    print(f"Error converting video: {result.stderr}")
                    return {}
                    
                print("Conversion successful!")
                # Use the converted file for processing
                video_path = output_path
                
            except Exception as e:
                print(f"Error during video conversion: {e}")
                return {}
        
        # Get video duration
        video = cv2.VideoCapture(video_path)
        if not video.isOpened():
            print(f"Error: Could not open video file at path: {video_path}")
            print(f"Current working directory: {os.getcwd()}")
            print(f"File exists: {os.path.exists(video_path)}")
            return {}
            
        fps = video.get(cv2.CAP_PROP_FPS)
        total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        print(f"FPS: {fps}")
        print(f"Total frames: {total_frames}")
        
        if fps == 0:
            print("Error: Invalid FPS value")
            return {}
            
        duration = total_frames / fps
        video.release()
        
        print(f"Video duration: {duration:.2f} seconds")
        print(f"Processing in {self.block_duration}-second blocks...")

        # Initialize results dictionary
        results = {}
        
        # Process audio first
        print("\nProcessing audio...")
        try:
            video_clip = VideoFileClip(video_path)
            audio = video_clip.audio
            
            current_block = 0
            while True:
                start_time = current_block * self.block_duration
                if start_time >= duration:
                    break
                
                end_time = min((current_block + 1) * self.block_duration, duration)
                block_key = f"{start_time:.1f}-{end_time:.1f}"
                
                print(f"Processing audio block {current_block + 1}")
                transcription = self.process_audio_segment(audio, start_time, end_time)
                
                results[block_key] = {
                    'transcription': transcription,
                    'emotion': None
                }
                
                current_block += 1
            
            video_clip.close()
            
        except Exception as e:
            print(f"Error in audio processing: {e}")
            return {}

        # Process video second
        print("\nProcessing video...")
        current_block = 0
        while True:
            start_time = current_block * self.block_duration
            if start_time >= duration:
                break
            
            end_time = min((current_block + 1) * self.block_duration, duration)
            block_key = f"{start_time:.1f}-{end_time:.1f}"
            
            print(f"Processing video block {current_block + 1}")
            emotion = self.process_video_frames(video_path, start_time, end_time)
            
            if block_key in results:
                results[block_key]['emotion'] = emotion
            else:
                results[block_key] = {
                    'emotion': emotion,
                    'transcription': None
                }
            
            current_block += 1

        return results

def main():
    detector = MultimodalDetector()
    video_path = "vid2.mp4"  # File in the same directory as the script
    print(f"Processing video: {video_path}")
    print(f"File exists: {os.path.exists(video_path)}")
    
    results = detector.process_video(video_path)
    
    print("\nFinal Results:")
    for time_block, data in results.items():
        print(f"\nTime block: {time_block}")
        print(f"Emotion: {data['emotion']}")
        print(f"Transcription: {data['transcription']}")

if __name__ == "__main__":
    main()