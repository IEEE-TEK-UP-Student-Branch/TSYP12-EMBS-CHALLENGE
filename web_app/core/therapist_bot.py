import chromadb
from chromadb.config import Settings
import ollama
import json
from typing import List, Dict
import textwrap
import os
from datetime import datetime
from pathlib import Path

class TherapistBot:
    def __init__(self, chroma_db_path: str):
        # Initialize Chroma client with persistence
        self.client = chromadb.PersistentClient(path=chroma_db_path)
        
        # Get or create the collection for mental health documents
        self.collection = self.client.get_or_create_collection(
            name="pdf_paragraphs",
            metadata={"hnsw:space": "cosine"}
        )
        
        # Initialize conversation memory
        self.conversation_history = []
        self.session_start_time = datetime.now()
        self.session_issues = set()  # Track discussed issues
        self.given_advice = []       # Track given advice
        self.session_duration_minutes = 5  # Demo session length
        
        # System prompt for the therapist persona
        self.system_prompt = """You are an experienced, empathetic mental health therapist conducting a brief demo therapy session.
        Follow these therapeutic guidelines:
        - Use active listening and reflection techniques
        - Provide quick, actionable advice when appropriate
        - Tag main issues with #ISSUE: tag (at the end of generation)
        - Tag advice with #ADVICE: tag (at the end of generation)
        - NEVER include 'Therapist:' or 'Patient:' in your responses
        - NEVER make up or imagine patient responses
        - ONLY respond to what the patient actually says
        
        Time Management Guidelines (5-minute demo session):
        - First 1-2 minutes: Quick rapport and identify main concern
        - Middle 2 minutes: Brief exploration and immediate guidance
        - Last 1 minute: Quick summary and key recommendation
        
        Remember: This is a demo session. Be concise and focused."""
        
    def get_embedding(self, text: str) -> List[float]:
        """Get embeddings using Ollama's Mistral model."""
        response = ollama.embeddings(
            model='mistral-nemo:12b-instruct-2407-q2_K',
            prompt=text
        )
        return response['embedding']
        
    def get_relevant_context(self, query: str, n_results: int = 2) -> str:
        """Retrieve relevant information from the knowledge base."""
        # Get embedding for the query
        query_embedding = self.get_embedding(query)
        
        # Query the collection
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        
        # Combine the retrieved documents into a single context string
        if results and results['documents']:
            context = "\n".join(results['documents'][0])
            return context
        return ""

    def format_conversation_history(self) -> str:
        """Format the recent conversation history for context."""
        # Only include the last 4 exchanges to maintain focus on recent context
        recent_history = self.conversation_history
        formatted_history = ""
        for entry in recent_history:
            formatted_history += f"User: {entry['user']}\nResponse: {entry['response']}\n"
        return formatted_history

    def extract_tags(self, text: str) -> tuple:
        """Extract issues and advice from the response."""
        issues = []
        advice = []
        
        for line in text.split('\n'):
            if '#ISSUE:' in line:
                issues.append(line.split('#ISSUE:')[1].strip())
            elif '#ADVICE:' in line:
                advice.append(line.split('#ADVICE:')[1].strip())
        
        return issues, advice

    def generate_session_report(self) -> str:
        """Generate a session report using the LLM."""
        prompt = f"""As a therapist, analyze this session and provide a concise summary. Include:
1. Main issues identified; describe why they were identified.
2. Key advice given; describe the advice's relationship to one of the identified issues.
3. Brief progress assessment.
4. Recommendations for future sessions.

Always remmember to direct the report to the patient.

Session history:
{self.format_conversation_history()}

Issues discussed: {', '.join(self.session_issues)}
Advice given: {', '.join(self.given_advice)}
"""
        try:
            response = ollama.generate(
                model='mistral-nemo:12b-instruct-2407-q2_K',
                prompt=prompt,
            )
            return response['response'].strip()
        except Exception as e:
            return f"Error generating report: {str(e)}"

    def process_user_message(self, user_input: str) -> dict:
        """Process a user message and return a response with session status."""
        # Check if session should end
        if self.should_end_session():
            return {
                "response": "Our session time has ended. I'll generate a detailed summary for you in a moment.",
                "session_ended": True,
                "session_status": self.get_session_status(),
                "generate_report": True  # Signal that a report should be generated
            }

        # Generate response
        prompt = self.generate_response(user_input)
        response = ollama.generate(
            model='mistral-nemo:12b-instruct-2407-q2_K',
            prompt=prompt,
        )
        response_text = response['response']

        # Clean up the response
        response_text = response_text.replace('Therapist:', '').replace('Patient:', '').strip()
        
        # Extract and store issues and advice
        issues, advice = self.extract_tags(response_text)
        self.session_issues.update(issues)
        self.given_advice.extend(advice)

        # Store conversation
        self.conversation_history.append({
            'user': user_input,
            'response': response_text
        })

        return {
            "response": response_text,
            "session_ended": False,
            "session_status": self.get_session_status()
        }

    def generate_response(self, user_input: str) -> str:
        """Generate a therapeutic response using the Mistral model and RAG."""
        # Get time information
        minutes_remaining, seconds_remaining = self.get_time_remaining()
        session_phase = self.get_session_phase()
        
        # Get relevant context from the knowledge base
        context = self.get_relevant_context(user_input)
        
        # Get conversation history
        conversation_context = self.format_conversation_history()
        
        # Construct the prompt with context and user input
        prompt = f"""{self.system_prompt}

        Session Time Remaining: {minutes_remaining} minutes, {seconds_remaining} seconds
        Session Phase: {session_phase}
        Previous conversation:
        {conversation_context}
        
        Relevant therapeutic knowledge:
        {context}

        User: {user_input}

        Response (be very brief, include #ISSUE and #ADVICE tags when appropriate):"""
        
        if minutes_remaining <= 1:
            prompt += """
            
            Note: Demo session ending soon. Provide one final key recommendation."""
        
        return prompt

    def start_new_session(self):
        """Start a new therapy session."""
        self.conversation_history = []
        self.session_start_time = datetime.now()
        self.session_issues = set()
        self.given_advice = []

    def get_session_status(self) -> dict:
        """Get current session status."""
        minutes_remaining, seconds_remaining = self.get_time_remaining()
        return {
            "session_active": not self.should_end_session(),
            "minutes_remaining": minutes_remaining,
            "seconds_remaining": seconds_remaining,
            "session_phase": self.get_session_phase(),
            "issues_discussed": list(self.session_issues),
            "advice_given": self.given_advice
        }

    def get_remaining_session_time(self) -> float:
        """Get remaining session time in minutes."""
        minutes, seconds = self.get_time_remaining()
        return minutes + (seconds / 60)

    def start_session(self):
        """Start an interactive therapy session."""
        print(f"\nTherapist: Welcome to this {self.session_duration_minutes}-minute demo therapy session.")
        print("While brief, I'm here to listen and provide support. Remember that I'm an AI assistant")
        print("and real concerns should be discussed with a licensed professional.")
        print("What's on your mind today?")
        
        while True:
            if self.should_end_session():
                print("\nTherapist: Our demo session time is up. Let me quickly summarize:")
                
                # Generate and save session report
                report = self.generate_session_report()
                report_path = self.save_session_report(report)
                
                if self.session_issues:
                    print("\nMain Issue Identified:")
                    print(f"- {next(iter(self.session_issues))}")  # Show the first issue
                
                if self.given_advice:
                    print("\nKey Recommendation:")
                    print(f"- {self.given_advice[-1]}")  # Show the last piece of advice
                
                print(f"\nA detailed session report is available at: {report_path}")
                print("\nThank you for trying this demo. Remember, this was a brief demonstration,")
                print("and real therapy sessions are typically longer and more comprehensive.")
                break
            
            minutes, seconds = self.get_time_remaining()
            if minutes <= 1 and len(self.conversation_history) % 2 == 0:  # Remind about time periodically
                print(f"\nTherapist: We have about {minutes} minute remaining in our demo. ")
            
            user_input = input("\nYou: ").strip()
            
            if user_input.lower() in ['exit', 'quit', 'bye']:
                # Generate and save session report
                report = self.generate_session_report()
                report_path = self.save_session_report(report)
                
                break
                
            print("\nTherapist: ", end='', flush=True)
            response = self.process_user_message(user_input)
            print(response["response"])

    def save_session_report(self, report: str):
        """Save the session report to a file."""
        # Create reports directory if it doesn't exist
        reports_dir = Path("therapy_reports")
        reports_dir.mkdir(exist_ok=True)
        
        # Generate filename with timestamp
        filename = f"session_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        report_path = reports_dir / filename
        
        # Save report
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        return report_path

    def get_time_remaining(self) -> tuple:
        """Get remaining session time in minutes and seconds."""
        elapsed = datetime.now() - self.session_start_time
        remaining = max(0, self.session_duration_minutes * 60 - elapsed.total_seconds())
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        return minutes, seconds

    def should_end_session(self) -> bool:
        """Check if session should end based on time."""
        minutes, _ = self.get_time_remaining()
        return minutes <= 0

    def get_session_phase(self) -> str:
        """Determine the current phase of the therapy session."""
        elapsed_minutes = (datetime.now() - self.session_start_time).total_seconds() / 60
        
        if elapsed_minutes < 2:
            return "initial"
        elif elapsed_minutes > self.session_duration_minutes - 1:
            return "closing"
        else:
            return "middle"
