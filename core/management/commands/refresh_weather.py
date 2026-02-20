"""
Refresh weather cache for active projects (geocode + fetch 7-day forecast).
Uses get_forecast_for_project with force_refresh=True (Open-Meteo, precipitation_probability_max).
Usage: python manage.py refresh_weather
       python manage.py refresh_weather --project_id 1
"""
from django.core.management.base import BaseCommand
from projects.models import Project
from core.weather_utils import get_forecast_for_project


class Command(BaseCommand):
    help = 'Geocode project addresses and fetch 7-day weather forecast (Open-Meteo).'

    def add_arguments(self, parser):
        parser.add_argument('--project_id', type=str, default='', help='Refresh only this project ID.')

    def handle(self, *args, **options):
        qs = Project.objects.filter(status=Project.STATUS_ACTIVE)
        if options.get('project_id'):
            qs = qs.filter(pk=options['project_id'])
        for project in qs:
            result = get_forecast_for_project(project, force_refresh=True)
            if result:
                self.stdout.write(f'Cached: {project.project_number}')
            else:
                self.stdout.write(f'Skipped (no address) or failed: {project.project_number}')
