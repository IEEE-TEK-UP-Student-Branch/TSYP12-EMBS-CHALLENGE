from django.contrib import admin
from .models import UserProfile, ChatMessage, ChatSession, Report

# Register your models here.

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'preferred_name', 'has_completed_onboarding', 'created_at')
    list_filter = ('has_completed_onboarding',)
    search_fields = ('user__username', 'preferred_name')

@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'topic', 'created_at', 'ended_at')
    list_filter = ('topic', 'ended_at')
    search_fields = ('user__username', 'topic')

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'session', 'is_ai', 'content_preview', 'created_at')
    list_filter = ('is_ai', 'created_at')
    search_fields = ('content', 'user__username')

    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content Preview'

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'status', 'created_at', 'completed_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'title', 'analysis_text')
    readonly_fields = ('created_at', 'completed_at')
