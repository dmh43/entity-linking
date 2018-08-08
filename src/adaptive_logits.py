import torch
from torch import nn
from torch.nn import functional as F


class AdaptiveLogits(nn.Module):
  """Logits calculation
  Args:
    vocab: tensor containing the vector representation of the vocabulary (eg the word embeddings) sorted by frequency
    cutoffs: list of cutoff indices for each cluster when words are sorted by decreasing frequency
    reduce_factor: dimension reduction factor of each tail bucket. Default: 4

  Shape:
    - hidden: (batch_size, hidden_size)
    - targets: (batch_size)
    - vocab: (vocab_size, hidden_size)
    - all_logits: [(batch_size, cutoffs[0] + len(cutoffs) - 1), (batch_size * p_t1, cutoffs[1] - cutoffs[0]), ...]

  Attributes:
    head: the learnable weights of the module for head bucket
    tail: the learnable weights of the module for tail buckets
  """

  def __init__(self, vocab, cutoffs, reduce_factor=4, device=None):
    super().__init__()
    if device is None:
      self.device = vocab.device
    else:
      self.device = device
    self.other_modules = nn.ModuleList()
    self.id = []
    self.cutoffs = cutoffs
    self.head = self._get_head_calc(vocab, cutoffs)
    self.tail = self._get_tail_calc(vocab, cutoffs, reduce_factor)

  def _get_head_calc(self, vocab, cutoffs):
    hidden_size = vocab.shape[1]
    shortlist = vocab[:cutoffs[0]]
    tail_vectors = nn.Linear(hidden_size, len(cutoffs[1:]), bias=False).to(self.device)
    self.other_modules.append(tail_vectors)
    def head_calc(hidden):
      shortlist_result = torch.mm(hidden, torch.transpose(shortlist, 0, 1))
      tail_vectors_result = tail_vectors(hidden)
      return torch.cat((shortlist_result, tail_vectors_result), 1)
    return head_calc

  def _get_tail_calc(self, vocab, cutoffs, reduce_factor):
    hidden_size = vocab.shape[1]
    tail = []
    for i in range(len(cutoffs) - 1):
      if reduce_factor == 1:
        tail_cluster = vocab[cutoffs[i] : cutoffs[i + 1]]
        def seq(hidden, tail_cluster=tail_cluster):
          return torch.mm(hidden, torch.transpose(tail_cluster, 0, 1))
      else:
        down = nn.Linear(hidden_size,
                         hidden_size // reduce_factor ** i,
                         bias=False).to(self.device)
        self.other_modules.append(down)
        decode_weight = down(vocab[cutoffs[i] : cutoffs[i + 1]])
        def seq(hidden, down=down, decode_weight=decode_weight):
          return torch.mm(down(hidden), torch.transpose(decode_weight, 0, 1))
      tail.append(seq)
    return tail

  def _set_targets(self, targets):
    self.id = []
    for i in range(len(self.cutoffs) - 1):
      mask = targets.ge(self.cutoffs[i]).mul(targets.lt(self.cutoffs[i + 1]))
      if mask.any():
        self.id.append(mask.float().nonzero().squeeze(1))
      else:
        self.id.append(None)

  def forward(self, hidden, targets):
    all_logits = [self.head(hidden)]
    self._set_targets(targets)
    for i in range(len(self.id)):
      if self.id[i] is not None:
        all_logits.append(self.tail[i](hidden.index_select(0, self.id[i])))
      else:
        all_logits.append(None)
    return all_logits

  def _remap_targets(self, targets):
    new_targets = [targets.clone()]
    for i in range(len(self.cutoffs) - 1):
      mask = targets.ge(self.cutoffs[i]).mul(targets.lt(self.cutoffs[i + 1]))
      new_targets[0][mask] = self.cutoffs[0] + i
      if mask.any():
        new_targets.append(targets[mask].add(-self.cutoffs[i]))
      else:
        new_targets.append(None)
    return new_targets

  def loss(self, all_logits, targets):
    batch_size = all_logits[0].size(0)
    targets = self._remap_targets(targets.data)
    output = 0.0
    for i in range(len(all_logits)):
      if all_logits[i] is not None:
        assert targets[i].min() >= 0 and targets[i].max() < all_logits[i].size(1)
        output = output + F.cross_entropy(all_logits[i],
                                          targets[i],
                                          size_average=False)
    output /= batch_size
    return output
