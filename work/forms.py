from datetime import date
from decimal import Decimal
from django import forms
from django.contrib.auth import get_user_model
from projects.models import Project
from .models import WorkItem

User = get_user_model()


class CompleteTaskTimeForm(forms.Form):
    """Date, hours, and notes when completing a task and logging time."""
    date_worked = forms.DateField(
        label='Date worked',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    hours = forms.DecimalField(
        label='Hours',
        min_value=Decimal('0'),
        max_digits=6,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'min': '0', 'step': '0.25', 'class': 'form-control'}),
    )
    notes = forms.CharField(
        label='Notes',
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
    )


class WorkItemForm(forms.ModelForm):
    class Meta:
        model = WorkItem
        fields = (
            'project', 'title', 'work_type', 'task_type_other', 'priority', 'due_date',
            'meeting_at', 'status', 'assigned_to', 'requested_by', 'notes',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['task_type_other'].required = False
        self.fields['task_type_other'].help_text = 'Optional. Only used when Task type is "Other".'
        self.fields['project'].required = False
        self.fields['project'].help_text = 'Optional. Leave blank for non-project tasks.'
        self.fields['project'].queryset = Project.objects.order_by('project_number')
        self.fields['title'].help_text = 'Required.'
        self.fields['work_type'].help_text = 'Required. Select a type or "Other".'
        self.fields['due_date'].help_text = 'Optional.'
        self.fields['meeting_at'].help_text = 'Optional.'
        self.fields['assigned_to'].help_text = 'Optional.'
        self.fields['requested_by'].help_text = 'Optional.'
        self.fields['notes'].help_text = 'Optional.'
        self.fields['project'].label_from_instance = lambda obj: f"{obj.project_number} — {obj.name}"
        self.fields['assigned_to'].queryset = User.objects.filter(username__in=['Mathias', 'scheduler1']).order_by('username')
        self.fields['due_date'].widget = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        self.fields['meeting_at'].required = False
        self.fields['meeting_at'].widget = forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'})
        for name in self.fields:
            self.fields[name].widget.attrs.setdefault('class', 'form-control')

