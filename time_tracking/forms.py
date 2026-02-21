from django import forms
from work.models import WorkItem
from .models import TimeEntry


class TimeEntryForm(forms.ModelForm):
    class Meta:
        model = TimeEntry
        fields = ('project', 'work_code', 'work_item', 'date', 'hours', 'description')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['work_item'].required = False
        self.fields['work_item'].queryset = WorkItem.objects.select_related('project').all()
        self.fields['project'].required = False
        self.fields['work_code'].required = False
        self.fields['date'].widget = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        self.fields['hours'].widget.attrs.update({'min': '0', 'step': '0.01'})
        for name in self.fields:
            self.fields[name].widget.attrs.setdefault('class', 'form-control')

    def clean_hours(self):
        value = self.cleaned_data.get('hours')
        if value is not None and value < 0:
            raise forms.ValidationError('Hours cannot be negative.')
        return value