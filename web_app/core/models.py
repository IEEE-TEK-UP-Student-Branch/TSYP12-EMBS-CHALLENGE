from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid

# Create your models here.

class UserProfile(models.Model):
    STRUGGLE_CHOICES = [
        ('anxiety', 'Anxiety'),
        ('stress', 'Stress'),
        ('sleep', 'Sleep'),
        ('depression', 'Depression'),
        ('selfcare', 'Self Care'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    has_completed_onboarding = models.BooleanField(default=False)
    preferred_name = models.CharField(max_length=50, blank=True)
    struggling_with = models.CharField(max_length=20, choices=STRUGGLE_CHOICES, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username}'s profile"

class ChatSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    topic = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        topic_str = f" about {self.topic}" if self.topic else ""
        return f"Chat with {self.user.username}{topic_str} on {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    def end_session(self):
        self.ended_at = timezone.now()
        self.save()

class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages', null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    is_ai = models.BooleanField(default=False)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        sender = "Momo" if self.is_ai else self.user.username
        return f"{sender}: {self.content[:50]}..."
    
    def save(self, *args, **kwargs):
        # If no session is set and we're saving a new message, create a legacy session
        if not self.session and not self.pk:
            self.session = ChatSession.objects.create(
                user=self.user,
                topic='legacy',
                created_at=self.created_at or timezone.now(),
                ended_at=self.created_at or timezone.now()
            )
        super().save(*args, **kwargs)

class Report(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Analysis'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    video = models.FileField(upload_to='reports/videos/', null=True, blank=True)
    title = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    analysis = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Report by {self.user.username} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    message = models.TextField()
    link = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Notification: {self.title} for {self.user.username}"