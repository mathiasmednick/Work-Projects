from django import forms
from .models import Project


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = (
            'project_number', 'name',
            'address_line1', 'address_line2', 'city', 'state', 'zip_code', 'country',
            'client', 'pm', 'status', 'notes',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.fields:
            self.fields[name].widget.attrs.setdefault('class', 'form-control')
        self.fields['address_line2'].required = False
        self.fields['country'].required = False

    def clean(self):
        data = super().clean()
        # Require address only on create so legacy projects without address can be saved on edit
        if not self.instance.pk:
            for f in ('address_line1', 'city', 'state', 'zip_code'):
                if not (data.get(f) or '').strip():
                    self.add_error(f, 'Required for project address.')
        return data