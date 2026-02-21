from django.db import models
from django.conf import settings


class Profile(models.Model):
    MANAGER = 'manager'
    SCHEDULER = 'scheduler'
    ROLE_CHOICES = [
        (MANAGER, 'Manager'),
        (SCHEDULER, 'Scheduler'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=SCHEDULER)

    class Meta:
        db_table = 'core_profile'

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


class AuditLog(models.Model):
    ACTION_CREATE = 'create'
    ACTION_UPDATE = 'update'
    ACTION_DELETE = 'delete'
    ACTION_RESTORE = 'restore'
    ACTION_CHOICES = [
        (ACTION_CREATE, 'Create'),
        (ACTION_UPDATE, 'Update'),
        (ACTION_DELETE, 'Delete'),
        (ACTION_RESTORE, 'Restore'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_logs',
    )
    model_name = models.CharField(max_length=50)  # e.g. 'workitem', 'project'
    object_id = models.PositiveIntegerField()
    object_repr = models.CharField(max_length=300)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'core_auditlog'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.get_action_display()} {self.model_name}#{self.object_id} by {self.user_id} at {self.timestamp}"


class Board(models.Model):
    """Whiteboard container. Multiple boards per site."""
    name = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_boards',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'core_board'

    def __str__(self):
        return self.name or f"Board {self.pk}"


class WhiteboardCard(models.Model):
    """Draggable card on a board. x,y in pixels."""
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='cards')
    x = models.IntegerField(default=0)
    y = models.IntegerField(default=0)
    text = models.TextField(blank=True)  # legacy; prefer title+body
    title = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)
    color = models.CharField(max_length=30, blank=True)
    linked_project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='whiteboard_cards',
    )
    link_to_board = models.ForeignKey(
        Board,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='linked_cards',
    )
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='whiteboard_cards',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'core_whiteboardcard'
        ordering = ['id']

    def display_title(self):
        if self.title:
            return self.title
        if self.linked_project:
            return f"{self.linked_project.project_number} {self.linked_project.name}"
        return (self.text or '(empty)')[:50]

    def __str__(self):
        return self.display_title()


class WhiteboardItem(models.Model):
    """Canvas item: sticky note, text, or box. Used by new canvas UI."""
    TYPE_NOTE = 'NOTE'
    TYPE_TEXT = 'TEXT'
    TYPE_BOX = 'BOX'
    TYPE_CHOICES = [
        (TYPE_NOTE, 'Note'),
        (TYPE_TEXT, 'Text'),
        (TYPE_BOX, 'Box'),
    ]
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='items')
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_NOTE)
    x = models.FloatField(default=0)
    y = models.FloatField(default=0)
    w = models.FloatField(default=120)
    h = models.FloatField(default=80)
    content = models.TextField(blank=True)
    color = models.CharField(max_length=30, blank=True)
    shape = models.CharField(max_length=20, blank=True, default='')
    text_style = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'core_whiteboarditem'
        ordering = ['id']

    def __str__(self):
        return f"{self.get_type_display()} at ({self.x},{self.y})"


class WhiteboardLink(models.Model):
    """Connector between two WhiteboardItems."""
    STYLE_ARROW = 'arrow'
    STYLE_PLAIN = 'plain'
    STYLE_CHOICES = [(STYLE_ARROW, 'Arrow'), (STYLE_PLAIN, 'Plain')]
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='links')
    from_item = models.ForeignKey(
        WhiteboardItem,
        on_delete=models.CASCADE,
        related_name='outgoing_links',
    )
    to_item = models.ForeignKey(
        WhiteboardItem,
        on_delete=models.CASCADE,
        related_name='incoming_links',
    )
    style = models.CharField(max_length=20, choices=STYLE_CHOICES, default=STYLE_ARROW)
    label = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        db_table = 'core_whiteboardlink'

    def __str__(self):
        return f"{self.from_item_id} -> {self.to_item_id}"


class ProjectWeatherLocation(models.Model):
    """Cached lat/lon for a project (from geocoding)."""
    project = models.OneToOneField(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='weather_location',
    )
    lat = models.DecimalField(max_digits=9, decimal_places=6)
    lon = models.DecimalField(max_digits=9, decimal_places=6)
    geocode_source = models.CharField(max_length=100, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'core_projectweatherlocation'


class ProjectWeatherCache(models.Model):
    """Cached 7-day forecast for a project."""
    project = models.OneToOneField(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='weather_cache',
    )
    forecast_json = models.TextField(blank=True)
    fetched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'core_projectweathercache'
