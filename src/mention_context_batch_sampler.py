from random import shuffle
import random
from collections import defaultdict

from torch.utils.data.sampler import Sampler
import pydash as _


class MentionContextBatchSampler(Sampler):
  def __init__(self, cursor, page_id_order, batch_size, min_mentions, limit=None, use_fast_sampler=False):
    super(MentionContextBatchSampler, self).__init__([])
    self.cursor = cursor
    self.page_id_order = page_id_order
    self.batch_size = batch_size
    self.page_ctr = 0
    self.ids_from_last_page = set()
    self.ids = []
    self.limit = limit
    self.num_mentions_seen = 0
    self._page_mention_ids = defaultdict(list)
    self.min_mentions = min_mentions
    self.use_fast_sampler = use_fast_sampler

  def __len__(self):
    raise NotImplementedError

  def __iter__(self):
    while self.page_ctr < len(self.page_id_order) or not _.is_empty(self.ids_from_last_page):
      if self.use_fast_sampler: yield [None] * self.batch_size
      if (self.limit is not None) and (self.num_mentions_seen >= self.limit): return
      batch = self._get_next_batch()
      yield batch
      self.num_mentions_seen += len(batch)

  def _get_page_mention_ids(self, page_id, page_ctr):
    if page_id in self._page_mention_ids:
      return self._page_mention_ids[page_id]
    else:
      self.cursor.execute(f'select mention_id, entity_id, page_id from entity_mentions_text em join entities e on em.entity_id = e.id where e.num_mentions > {self.min_mentions} and page_id in (' + str(self.page_id_order[page_ctr : page_ctr + 10000])[1:-1] + ')')
      self._page_mention_ids = defaultdict(list)
      for row in self.cursor.fetchall():
        self._page_mention_ids[row['page_id']].append(row['mention_id'])
      return self._page_mention_ids[page_id]

  def _get_next_batch(self):
    ids = []
    if len(self.ids_from_last_page) > self.batch_size:
      ids = random.sample(list(self.ids_from_last_page), self.batch_size)
      self.ids_from_last_page = self.ids_from_last_page - set(ids)
      shuffle(ids)
      return ids
    else:
      if not _.is_empty(self.ids_from_last_page):
        ids = list(self.ids_from_last_page)
        self.ids_from_last_page = set()
        if self.page_ctr > len(self.page_id_order):
          return ids
      for page_id in self.page_id_order[self.page_ctr:]:
        self.page_ctr += 1
        page_mention_ids = self._get_page_mention_ids(page_id, self.page_ctr)
        ids.extend(page_mention_ids)
        if len(ids) >= self.batch_size:
          self.ids_from_last_page = set(ids[self.batch_size:])
          ids = ids[:self.batch_size]
          shuffle(ids)
          return ids
        else:
          self.ids_from_last_page = set()
      ids = ids[:]
      shuffle(ids)
      return ids
