import getopt
import os
import sys

from dotenv import load_dotenv
from pyrsistent import m
import pydash as _
import torch

from runner import Runner

args_with_values =  [{'name': 'batch_size'                 , 'for': 'train_param', 'type': int},
                     {'name': 'dataset_limit'              , 'for': 'train_param', 'type': lambda limit: int(limit) if limit is not None else None},
                     {'name': 'dropout_drop_prob'          , 'for': 'train_param', 'type': float},
                     {'name': 'train_size'                 , 'for': 'train_param', 'type': float},
                     {'name': 'clip_grad'                  , 'for': 'train_param', 'type': float},
                     {'name': 'num_epochs'                 , 'for': 'train_param', 'type': int},
                     {'name': 'min_mentions'               , 'for': 'train_param', 'type': int},
                     {'name': 'start_from_page_num'        , 'for': 'train_param', 'type': int},
                     {'name': 'ablation'                   , 'for': 'model_param', 'type': lambda string: string.split(',')},
                     {'name': 'document_encoder_lstm_size' , 'for': 'model_param', 'type': int},
                     {'name': 'embed_len'                  , 'for': 'model_param', 'type': int},
                     {'name': 'local_encoder_lstm_size'    , 'for': 'model_param', 'type': int},
                     {'name': 'num_candidates'             , 'for': 'model_param', 'type': int},
                     {'name': 'num_lstm_layers'            , 'for': 'model_param', 'type': int},
                     {'name': 'num_cnn_local_filters'      , 'for': 'model_param', 'type': int},
                     {'name': 'word_embed_len'             , 'for': 'model_param', 'type': int},
                     {'name': 'word_embedding_set'         , 'for': 'model_param', 'type': str},
                     {'name': 'buffer_scale'               , 'for': 'run_param'  , 'type': int},
                     {'name': 'adaptive_softmax_cutoffs'   , 'for': 'model_param', 'type': lambda string: [int(cutoff) for cutoff in string.split(',')]},
                     {'name': 'load_path'                  , 'for': 'run_param', 'type': lambda string: str(string) if string is not None else string},
                     {'name': 'comments'                   , 'for': 'run_param', 'type': str}]

runner = None
def main():
  global runner
  device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
  load_dotenv(dotenv_path='.env')
  flag_argnames = ['load_model',
                   'use_adaptive_softmax',
                   'use_fast_sampler',
                   'dont_use_hardcoded_cutoffs',
                   'use_ranking_loss',
                   'dont_use_deep_network',
                   'use_cnn_local',
                   'use_lstm_local',
                   'dont_freeze_word_embeddings',
                   'dont_continue_training',
                   'cheat',
                   'use_conll',
                   'use_wiki2vec']
  args = getopt.getopt(_.tail(sys.argv), '', flag_argnames + [arg['name'] + '=' for arg in args_with_values])[0]
  flags = [_.head(arg) for arg in args]
  train_params = m(use_fast_sampler='--use_fast_sampler' in flags)
  run_params = m(load_model='--load_model' in flags,
                 cheat='--cheat' in flags,
                 continue_training='--dont_continue_training' not in flags,
                 use_conll='--use_conll' in flags)
  model_params = m(use_adaptive_softmax='--use_adaptive_softmax' in flags,
                   use_hardcoded_cutoffs='--dont_use_hardcoded_cutoffs' not in flags,
                   use_ranking_loss='--use_ranking_loss' in flags,
                   use_cnn_local='--use_cnn_local' in flags,
                   use_lstm_local='--use_lstm_local' in flags,
                   use_deep_network='--dont_use_deep_network' not in flags,
                   freeze_word_embeddings='--dont_freeze_word_embeddings' not in flags,
                   use_wiki2vec='--use_wiki2vec' in flags)
  paths = m(lookups=os.getenv("LOOKUPS_PATH"),
            page_id_order=os.getenv("PAGE_ID_ORDER_PATH"))
  for arg in args_with_values:
    name = arg['name']
    pair = _.find(args, lambda pair: name in pair[0])
    if pair:
      parsed = arg['type'](pair[1])
      if arg['for'] == 'path':
        paths = paths.set(name, parsed)
      elif arg['for'] == 'model_param':
        model_params = model_params.set(name, parsed)
      elif arg['for'] == 'train_param':
        train_params = train_params.set(name, parsed)
      elif arg['for'] == 'run_param':
        run_params = run_params.set(name, parsed)
      else:
        raise ValueError('`args_with_values` contains unsupported param group ' + arg['for'])
  name_pair = _.find(args, lambda pair: 'name' in pair[0])
  name = name_pair[1] if name_pair else ''
  runner = Runner(device=device,
                  paths=paths,
                  train_params=train_params,
                  model_params=model_params,
                  run_params=run_params)
  runner.run()


if __name__ == "__main__":
  import ipdb
  import traceback
  import sys

  try:
    main()
  except: # pylint: disable=bare-except
    if (runner is not None) and (runner.encoder is not None):
      torch.save(runner.encoder.state_dict(), './' + runner.experiment.model_name + '_debug')
    extype, value, tb = sys.exc_info()
    traceback.print_exc()
    ipdb.post_mortem(tb)
