import torch
from torch import nn

from logits import Logits
from description_encoder_model import DescriptionEncoder

def test_description_encoder_forward():
  embed_len = 10
  word_embed_len = 15
  num_entities = 20
  batch_size = 2
  desc_len = 9
  pad_vector = torch.randn((word_embed_len, ))
  desc_enc = DescriptionEncoder(word_embed_len,
                                torch.nn.Embedding(num_entities,
                                                   embed_len,
                                                   _weight=torch.randn((num_entities, embed_len))),
                                pad_vector)
  descriptions = torch.randn((batch_size, desc_len, word_embed_len))
  desc_embeds = desc_enc(descriptions)
  assert desc_embeds.shape == torch.Size([2, embed_len])

def test_description_encoder_loss():
  embed_len = 10
  word_embed_len = 15
  num_entities = 20
  batch_size = 2
  desc_len = 9
  pad_vector = torch.randn((word_embed_len, ))
  entity_embeds = torch.nn.Embedding(num_entities,
                                     embed_len,
                                     _weight=torch.randn((num_entities, embed_len)))
  desc_enc = DescriptionEncoder(word_embed_len,
                                entity_embeds,
                                pad_vector)
  descriptions = torch.randn((batch_size, desc_len, word_embed_len))
  desc_embeds = desc_enc(descriptions)
  labels_for_batch = torch.arange(batch_size, dtype=torch.long)
  calc_logits = Logits()
  criterion = nn.CrossEntropyLoss()
  candidates = entity_embeds(torch.randint(0, num_entities, (batch_size,), dtype=torch.long))
  logits = calc_logits(desc_embeds, candidates)
  loss = criterion(logits, labels_for_batch)
  assert isinstance(loss, torch.Tensor)
  assert loss.shape == torch.Size([])
