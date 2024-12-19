from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Count
from django.contrib import messages
from .models import UserProfile, ChatMessage, Report, Notification, ChatSession
from datetime import timedelta
import os
from .therapist_bot import TherapistBot
from .synchronized_detection import MultimodalDetector
from .stress_sense_model import StressSenseModel
import json
from django.conf import settings
import yaml
import threading
import random

# Initialize the TherapistBot and MultimodalDetector
CHROMA_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'chroma')
bot = TherapistBot(CHROMA_DB_PATH)
detector = MultimodalDetector()
#stress_model = StressSenseModel()

# Get the prompts from YAML data
with open('agent_config.yaml', 'r') as file:
    agent_config = yaml.safe_load(file)

biometric_notification_shown = False

def get_base_context(request):
    """Get common context data for base template"""
    if request.user.is_authenticated:
        notifications_queryset = Notification.objects.filter(user=request.user)
        unread_notifications_count = notifications_queryset.filter(is_read=False).count()
        notifications = notifications_queryset.order_by('-created_at')[:5]
        return {
            'notifications': notifications,
            'unread_notifications_count': unread_notifications_count,
        }
    return {}

def create_biometric_notification(user):
    """Create a notification about biometric data after a delay"""
    def delayed_notification():
        delay = random.randint(1, 2) # 20 to 30 seconds
        threading.Event().wait(delay)
        
        # Set behavior agent prompt
        bot.system_prompt = agent_config['agents']['behavior']['prompt']
        
        # Get behavior from biometric data
        behavior = 'Nail_Biting' # Example behavior
        
        # Send message as if from user
        user_message = f"Based on biometric data, I tend to {behavior}. Tell me that you noticed this behavioral pattern and help me manage it."
        
        analysis = bot.process_user_message(user_message)
                
        # Create a new report
        report = Report.objects.create(
            user=user,
            title='Biometric Health Update',
            status='completed',
        )
        report.analysis = analysis["response"]
        report.save()
        
        Notification.objects.create(
            user=user,
            title='Behavioral Health Update',
            message=analysis["response"].split('\n')[0][:100] + "...",
            link=f'/report/view/{report.id}',
            is_read=False
        )
    
    # Start the notification thread
    thread = threading.Thread(target=delayed_notification)
    thread.daemon = True  # Thread will exit when main program exits
    thread.start()

def home(request):
    """Home view - redirects to dashboard if user is authenticated"""
    if request.user.is_authenticated:
        profile = UserProfile.objects.get_or_create(user=request.user)[0]
        if not profile.has_completed_onboarding:
            return redirect('onboarding')
        return redirect('dashboard')
    return render(request, 'core/home.html')

def register(request):
    """User registration view"""
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            UserProfile.objects.create(user=user)
            return redirect('onboarding')
    else:
        form = UserCreationForm()
    return render(request, 'core/register.html', {'form': form})

@login_required
def onboarding(request):
    """Onboarding view for new users to set their preferences"""
    profile = UserProfile.objects.get_or_create(user=request.user)[0]
    
    if profile.has_completed_onboarding:
        return redirect('dashboard')
    
    if request.method == 'POST':
        preferred_name = request.POST.get('preferred_name', '').strip()
        struggling_with = request.POST.get('struggling_with', '').strip()
        
        profile.preferred_name = preferred_name
        profile.struggling_with = struggling_with
        profile.has_completed_onboarding = True
        profile.save()
        
        if struggling_with:
            return redirect('topic_page', topic_slug=struggling_with)
        return redirect('dashboard')
    
    return render(request, 'core/onboarding.html')

@login_required
def dashboard(request):
    """Dashboard view showing mood trends and recent activity"""
    global biometric_notification_shown
    context = get_base_context(request)
    
    # Create biometrics notification
    if not biometric_notification_shown:
        Notification.objects.create(
            user=request.user,
            title='Smart watch connected successfully',
            message='Momo is reading your biometric data. ✅',
            link='/dashboard/',
            is_read=False
        )
        biometric_notification_shown = True
        # Start the delayed notification thread
        create_biometric_notification(request.user)
    
    return render(request, 'core/dashboard.html', context)

@login_required
@require_http_methods(["POST"])
def mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'status': 'success'})

@login_required
def report_record(request, report_id=None):
    """View for recording and submitting a video report"""
    context = get_base_context(request)
    
    # If no report_id, create a new report automatically
    if not report_id:
        # Generate a title with timestamp
        title = f"Report {timezone.now().strftime('%Y-%m-%d %H:%M')}"
        report = Report.objects.create(
            user=request.user,
            title=title,
            status='pending'
        )
        return redirect('report_record', report_id=report.id)
    
    # If report_id exists, handle video upload
    report = get_object_or_404(Report, id=report_id, user=request.user)
    
    if request.method == 'POST':
        video_file = request.FILES.get('video')
        if video_file:
            # Save the video file
            report.video = video_file
            report.status = 'processing'
            report.save()
            
            # Get the absolute path of the saved video file
            video_path = os.path.join(settings.MEDIA_ROOT, str(report.video))
            
            try:
                print(video_path)
                # Process the video using MultimodalDetector
                results = detector.process_video(video_path)
                print(results)
                # Prepare data for the LLM prompt
                emotions_summary = []
                speech_summary = []
                
                for time_block, data in results.items():
                    if data['emotion']:
                        emotions_summary.append(f"At {time_block}: {data['emotion']}")
                    if data['transcription']:
                        speech_summary.append(f"At {time_block}: {data['transcription']}")
                
                # Create a prompt for the LLM
                prompt = f"""
                Please analyze this therapy session recording and provide a comprehensive report. Here are the details:

                Emotional Analysis:
                {chr(10).join(emotions_summary)}

                Speech Content:
                {chr(10).join(speech_summary)}

                Based on the emotional patterns and speech content:
                1. Identify the main emotional states and their significance
                2. Analyze the key topics discussed
                3. Note any concerning patterns or positive developments
                4. Provide therapeutic insights and recommendations

                Please format the response in a clear, empathetic manner suitable for the client.
                """
                print(prompt)
                # Get analysis from the LLM
                analysis = bot.process_user_message(prompt)
                print(analysis)
                # Save the analysis to the report
                report.analysis = analysis["response"]
                report.status = 'completed'
                report.save()
                
                # Create notification
                Notification.objects.create(
                    user=request.user,
                    title='Report Analysis Complete',
                    message='Your video report has been analyzed. Click to view the insights.',
                    link=f'/report/view/{report.id}'
                )
                
            except Exception as e:
                report.status = 'failed'
                report.save()
                print(f"Error processing video: {e}")
                return JsonResponse({
                    'status': 'error',
                    'message': 'Error processing video'
                }, status=500)

            return JsonResponse({
                'status': 'success',
                'redirect_url': '/dashboard/',
                'message': 'Video uploaded and processed successfully'
            })
            
        return JsonResponse({
            'status': 'error',
            'message': 'Video file is required'
        }, status=400)
    
    return render(request, 'core/report_record.html', {
        'report': report,
        **context
    })

@login_required
def report_view(request, report_id):
    """View for displaying the AI analysis of a video report"""
    context = get_base_context(request)
    report = get_object_or_404(Report, id=report_id, user=request.user)
    
    # Mark notification as read if it exists
    Notification.objects.filter(
        user=request.user,
        link=f'/report/view/{report_id}'
    ).update(is_read=True)

    
    context.update({
        'report': report,
        'status': report.status,
        'analysis': report.analysis if report.status == 'completed' else None,
    })

    return render(request, 'core/report_view.html', context)

@login_required
def chat_view(request):
    """Chat view with Momo"""
    # End any existing active sessions and generate reports
    active_sessions = ChatSession.objects.filter(user=request.user, ended_at__isnull=True)
    for session in active_sessions:
        session.ended_at = timezone.now()
        session.save()
        
        # Generate report using TherapistBot
        bot.conversation_history = [
            {'user': msg.content, 'response': msg.content} 
            for msg in session.messages.all().order_by('created_at')
        ]
        report = bot.generate_session_report()
        bot.save_session_report(report)
        
        # Create a Report object
        report_obj = Report.objects.create(
            user=request.user,
            title=f"Consultation Report - {session.created_at.strftime('%Y-%m-%d %H:%M')}",
            status='completed',
            analysis=report,
            completed_at=timezone.now()
        )
        
        # Create notification
        Notification.objects.create(
            user=request.user,
            title='Session Report Available',
            message='Your consultation report has been generated and is ready for viewing.',
            link=f'/report/view/{report_obj.id}'
        )
    
    # Create a new session and start the bot
    topic = request.GET.get('topic')
    session = ChatSession.objects.create(user=request.user, topic=topic)
    bot.start_new_session()
    
    # Get topic-specific first message if applicable
    if topic:
        topic_messages = [
            'anxiety',
            'stress',
            'sleep',
            'depression',
            'selfcare',
            'crisis',
        ]
        if topic in topic_messages:
            bot.system_prompt = agent_config['agents'][topic]['prompt']
            initial_message = bot.process_user_message('I am struggling with ' + topic)['response']
            # Save AI response
            ChatMessage.objects.create(
                session=session,
                user=request.user,
                is_ai=True,
                content=initial_message
            )
            # Add to bot's conversation history
            bot.conversation_history.append({
                'user': '',
                'response': initial_message
            })
    
    context = {
        'messages': session.messages.all(),
        'topic': topic,
        'session': session,
        'session_status': bot.get_session_status(),
        **get_base_context(request)
    }
    return render(request, 'core/chat.html', context)

@require_POST
@login_required
def chat_message(request):
    """Handle new chat message"""
    try:
        message = request.POST.get('message', '').strip()
        if not message:
            return JsonResponse({'error': 'Message cannot be empty'}, status=400)
        
        # Get or create active session
        session = ChatSession.objects.filter(user=request.user, ended_at__isnull=True).first()
        if not session:
            session = ChatSession.objects.create(user=request.user)
            bot.start_new_session()
        
        # Check if session should end before processing message
        if bot.should_end_session():
            session.ended_at = timezone.now()
            session.save()
            
            # Generate and save report
            report = bot.generate_session_report()
            
            # Create Report object
            report_obj = Report.objects.create(
                user=request.user,
                title=f"Consultation Report - {session.created_at.strftime('%Y-%m-%d %H:%M')}",
                status='completed',
                analysis_text=report,
                completed_at=timezone.now()
            )
            
            # Create notification
            Notification.objects.create(
                user=request.user,
                title='Session Report Available',
                message='Your consultation report has been generated and is ready for viewing.',
                link=f'/report/view/{report_obj.id}'
            )
            
            return JsonResponse({
                'status': 'success',
                'session_ended': True,
                'redirect_url': '/dashboard/',
                'message': 'Your consultation report is being processed, access notifications tab to find the session report'
            })
        
        # Save user message
        user_message = ChatMessage.objects.create(
            session=session,
            user=request.user,
            content=message,
            is_ai=False
        )
        
        # Process message with TherapistBot
        response_data = bot.process_user_message(message)
        
        # Save AI response
        ai_message = ChatMessage.objects.create(
            session=session,
            user=request.user,
            content=response_data['response'],
            is_ai=True
        )
        
        # Get session timing information
        minutes_remaining, seconds_remaining = bot.get_time_remaining()
        session_phase = bot.get_session_phase()
        
        # Render message templates
        user_message_html = render_to_string(
            'core/chat_snippets/user_message.html',
            {'message': user_message}
        )
        
        ai_message_html = render_to_string(
            'core/chat_snippets/ai_message.html',
            {'message': ai_message}
        )
        
        return JsonResponse({
            'status': 'success',
            'session_ended': False,
            'messages': [
                {'type': 'user', 'html': user_message_html},
                {'type': 'ai', 'html': ai_message_html}
            ],
            'session_status': {
                'minutes_remaining': minutes_remaining,
                'seconds_remaining': seconds_remaining,
                'session_phase': session_phase,
                'should_end': bot.should_end_session()
            }
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_notifications(request):
    """API endpoint to get notifications"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    data = [{
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'link': n.link,
        'is_read': n.is_read,
        'created_at': n.created_at.isoformat()
    } for n in notifications]
    return JsonResponse(data, safe=False)

@login_required
def mark_all_notifications_read(request):
    """Mark all notifications as read and redirect back to notifications page"""
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return redirect('notifications')
    return redirect('notifications')

@login_required
def notifications_page(request):
    filter_type = request.GET.get('filter', 'all')
    
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    if filter_type == 'unread':
        notifications = notifications.filter(is_read=False)
    elif filter_type == 'read':
        notifications = notifications.filter(is_read=True)
    
    has_unread = Notification.objects.filter(user=request.user, is_read=False).exists()
    
    context = {
        'notifications': notifications,
        'filter': filter_type,
        'has_unread': has_unread
    }
    
    return render(request, 'core/notifications.html', context)

# Topic content dictionary
TOPIC_CONTENT = {
    'anxiety': {
        'title': 'Managing Anxiety',
        'emoji': '😌',
        'description': 'Learn effective techniques to manage anxiety and find calm in challenging moments.',
        'tips': [
            {'emoji': '🫁', 'title': 'Deep Breathing', 'description': 'Practice 4-7-8 breathing: Inhale for 4 seconds, hold for 7, exhale for 8.'},
            {'emoji': '🎯', 'title': 'Grounding Technique', 'description': 'Use the 5-4-3-2-1 method: Name 5 things you see, 4 you feel, 3 you hear, 2 you smell, 1 you taste.'},
            {'emoji': '🧊', 'title': 'Cold Water Reset', 'description': 'Splash cold water on your face or hold an ice cube to reset your nervous system.'},
            {'emoji': '🚶‍♂️', 'title': 'Walk it Out', 'description': 'Take a short walk, focusing on your steps and surroundings.'},
        ],
        'resources': [
            {'title': 'Anxiety & Depression Association', 'description': 'Expert resources and self-help tools', 'url': 'https://adaa.org'},
            {'title': 'Calm App', 'description': 'Guided meditations and breathing exercises', 'url': 'https://www.calm.com'},
        ]
    },
    'stress': {
        'title': 'Stress Relief',
        'emoji': '🧘',
        'description': 'Discover practical strategies to manage stress and maintain balance in your life.',
        'tips': [
            {'emoji': '📝', 'title': 'Brain Dump', 'description': 'Write down everything on your mind without judgment.'},
            {'emoji': '🎵', 'title': 'Music Break', 'description': 'Listen to calming music for 5-10 minutes.'},
            {'emoji': '💪', 'title': 'Progressive Relaxation', 'description': 'Tense and relax each muscle group from toes to head.'},
            {'emoji': '⏰', 'title': 'Time Blocking', 'description': 'Break your day into manageable chunks with breaks.'},
        ],
        'resources': [
            {'title': 'Headspace', 'description': 'Meditation and mindfulness exercises', 'url': 'https://www.headspace.com'},
            {'title': 'Stress Management Guide', 'description': 'Mayo Clinic\'s comprehensive guide', 'url': 'https://www.mayoclinic.org/healthy-lifestyle/stress-management/basics/stress-basics/hlv-20049495'},
        ]
    },
    'sleep': {
        'title': 'Better Sleep',
        'emoji': '😴',
        'description': 'Improve your sleep quality with proven techniques and healthy habits.',
        'tips': [
            {'emoji': '🌅', 'title': 'Consistent Schedule', 'description': 'Go to bed and wake up at the same time every day.'},
            {'emoji': '📱', 'title': 'Screen Wind-Down', 'description': 'Avoid screens 1 hour before bedtime.'},
            {'emoji': '🌡️', 'title': 'Cool Environment', 'description': 'Keep your bedroom between 60-67°F (15-19°C).'},
            {'emoji': '☕', 'title': 'Caffeine Cut-off', 'description': 'Avoid caffeine 6-8 hours before bedtime.'},
        ],
        'resources': [
            {'title': 'Sleep Foundation', 'description': 'Science-backed sleep information', 'url': 'https://www.sleepfoundation.org'},
            {'title': 'CBT-I Coach', 'description': 'Cognitive behavioral therapy for insomnia', 'url': 'https://mobile.va.gov/app/cbt-i-coach'},
        ]
    },
    'depression': {
        'title': 'Depression Support',
        'emoji': '🌅',
        'description': 'Find support and strategies to help manage depression and improve your well-being.',
        'tips': [
            {'emoji': '🌱', 'title': 'Small Steps', 'description': 'Set tiny, achievable goals for each day.'},
            {'emoji': '🤝', 'title': 'Reach Out', 'description': 'Connect with one person, even briefly.'},
            {'emoji': '🌞', 'title': 'Light Exposure', 'description': 'Get natural sunlight within the first hour of waking.'},
            {'emoji': '📅', 'title': 'Routine Building', 'description': 'Create a simple morning routine to start your day.'},
        ],
        'resources': [
            {'title': 'NAMI', 'description': 'National Alliance on Mental Illness resources', 'url': 'https://www.nami.org'},
            {'title': '7 Cups', 'description': 'Free emotional support', 'url': 'https://www.7cups.com'},
        ]
    },
    'selfcare': {
        'title': 'Self Care',
        'emoji': '💝',
        'description': 'Develop a personalized self-care routine that works for you.',
        'tips': [
            {'emoji': '🛁', 'title': 'Comfort Ritual', 'description': 'Create a relaxing self-care ritual you enjoy.'},
            {'emoji': '🚫', 'title': 'Boundaries', 'description': 'Practice saying no to protect your energy.'},
            {'emoji': '📱', 'title': 'Digital Detox', 'description': 'Take regular breaks from social media.'},
            {'emoji': '🎨', 'title': 'Creative Expression', 'description': 'Engage in any form of creativity you enjoy.'},
        ],
        'resources': [
            {'title': 'Self-Compassion', 'description': 'Dr. Kristin Neff\'s resources', 'url': 'https://self-compassion.org'},
            {'title': 'Happify', 'description': 'Science-based activities and games', 'url': 'https://www.happify.com'},
        ]
    },
    'crisis': {
        'title': 'Crisis Help',
        'emoji': '🆘',
        'description': 'Immediate support and resources for crisis situations.',
        'tips': [
            {'emoji': '📞', 'title': 'Call 988', 'description': 'The Suicide & Crisis Lifeline is available 24/7.'},
            {'emoji': '👥', 'title': 'Not Alone', 'description': 'Reach out to someone you trust or a professional.'},
            {'emoji': '🧠', 'title': 'Grounding', 'description': 'Focus on your immediate surroundings and breathe.'},
            {'emoji': '📍', 'title': 'Safe Place', 'description': 'Go to a safe place or contact emergency services.'},
        ],
        'resources': [
            {'title': 'Crisis Text Line', 'description': 'Text HOME to 741741', 'url': 'https://www.crisistextline.org'},
            {'title': 'Find a Therapist', 'description': 'Psychology Today\'s directory', 'url': 'https://www.psychologytoday.com/us/therapists'},
        ]
    }
}

@login_required
def topic_page(request, topic_slug):
    """View for topic-specific pages with tips and resources"""
    context = get_base_context(request)
    if topic_slug not in TOPIC_CONTENT:
        return redirect('dashboard')
        
    content = TOPIC_CONTENT[topic_slug]
    
    context.update({
        'topic_slug': topic_slug,
        'topic_title': content['title'],
        'topic_emoji': content['emoji'],
        'topic_description': content['description'],
        'tips': content['tips'],
        'resources': content['resources'],
        'ai_companion_name': "Momo"
    })
    
    return render(request, 'core/topic_page.html', context)