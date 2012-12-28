import copy
from django.db import models
from datetime import datetime
from django.db.models import Q
from django.db.models.query import QuerySet
from django.db.models.manager import Manager


class BitemporalQuerySet(QuerySet):

    def get(self, *args, **kwargs):
        if 'pk' in kwargs:
            kwargs['id'] = kwargs['pk']
            del kwargs['pk']

        return super(BitemporalQuerySet, self).get(*args, **kwargs)

    def during(self, valid_start, valid_end=None):
        if valid_end:
            condition = Q(valid_end_date__gte=valid_end)
        else:
            condition = (Q(valid_end_date__gte=valid_start) |
                    Q(valid_end_date=None))

        return self.filter(condition,
            valid_start_date__lte=valid_start, txn_end_date=None)

    def current(self):
        return self.during(datetime.now())


class BitemporalManager(Manager):

    def get_query_set(self):
        return BitemporalQuerySet(self.model, using=self._db)

    def current(self):
        return self.get_query_set().current()

    def during(self, valid_start, valid_end=None):
        return self.get_query_set().during(valid_start, valid_end)


class BitemporalModelBase(models.Model):

    objects = BitemporalManager()

    id = models.IntegerField(blank=True, null=True)
    row_id = models.AutoField(primary_key=True)

    valid_start_date = models.DateTimeField()
    valid_end_date = models.DateTimeField(blank=True, null=True)

    txn_start_date = models.DateTimeField(auto_now_add=True)
    txn_end_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        abstract = True
        unique_together = [
            ('id', 'valid_start_date', 'valid_end_date', 'txn_end_date'),
        ]

    def _clone(self):
        new_obj = copy.deepcopy(self)
        new_obj.row_id = None
        return new_obj

    def save(self, valid_start_date=None, valid_end_date=None,
            force_insert=False, force_update=False, using=None,
            update_fields=None):

        if not self.valid_start_date:
            self.valid_start_date = valid_start_date or datetime.now()

        self.save_base(using=using, force_insert=force_insert,
                       force_update=force_update, update_fields=None)

        if not self.id:
            self.id = self.row_id
            self.save_base(using=using, update_fields=('id',))

    def ammend(self):
        now = datetime.now()

        new_obj = self._clone()
        new_obj.txn_start_date = now

        self.txn_end_date = now

        new_obj.valid_end_date = self.valid_start_date

        self.save()
        new_obj.save()

        return new_obj

    def update(self):
        now = datetime.now()

        previous_date = self._clone()
        previous_date.valid_end_date = now
        previous_date.txn_end_date = None

        updated = self._clone()
        updated.valid_start_date = now
        updated.valid_end_date = None

        self.txn_end_date = now

        self.save()
        updated.save()
        previous_date.save()

        return updated
