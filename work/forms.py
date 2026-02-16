from datetime import date
from decimal import Decimal
from django import forms
from django.contrib.auth import get_user_model
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
            'status', 'assigned_to', 'requested_by', 'notes',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['task_type_other'].required = False
        self.fields['assigned_to'].queryset = User.objects.filter(username__in=['Mathias', 'scheduler1']).order_by('username')
        self.fields['due_date'].widget = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        for name in self.fields:
            self.fields[name].widget.attrs.setdefault('class', 'form-control')

    def clean(self):
        data = super().clean()
        if data.get('work_type') == WorkItem.WORK_TYPE_OTHER and not (data.get('task_type_other') or '').strip():
            self.add_error('task_type_other', 'Please specify the task type when selecting "Other".')
        return data
