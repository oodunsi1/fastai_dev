#AUTOGENERATED! DO NOT EDIT! File to edit: dev/04_data_core.ipynb (unless otherwise specified).

__all__ = ['get_files', 'FileGetter', 'image_extensions', 'get_image_files', 'ImageGetter', 'RandomSplitter',
           'GrandparentSplitter', 'parent_label', 'RegexLabeller', 'show_image', 'show_titled_image',
           'show_image_batch', 'TensorImage', 'Categorize', 'String', 'mk_string', 'get_samples', 'TfmdDL', 'Cuda',
           'TensorMask', 'ByteToFloatTensor', 'Normalize', 'DataBunch']

from ..imports import *
from ..test import *
from ..core import *
from .pipeline import *
from .external import *
from ..notebook.showdoc import show_doc

def _get_files(p, fs, extensions=None):
    p = Path(p)
    res = [p/f for f in fs if not f.startswith('.')
           and ((not extensions) or f'.{f.split(".")[-1].lower()}' in extensions)]
    return res

def get_files(path, extensions=None, recurse=True, include=None):
    "Get all the files in `path` with optional `extensions`, optionally with `recurse`."
    path = Path(path)
    extensions = setify(extensions)
    extensions = {e.lower() for e in extensions}
    if recurse:
        res = []
        for i,(p,d,f) in enumerate(os.walk(path)): # returns (dirpath, dirnames, filenames)
            if include is not None and i==0: d[:] = [o for o in d if o in include]
            else:                            d[:] = [o for o in d if not o.startswith('.')]
            res += _get_files(p, f, extensions)
    else:
        f = [o.name for o in os.scandir(path) if o.is_file()]
        res = _get_files(path, f, extensions)
    return L(res)

def FileGetter(suf='', extensions=None, recurse=True, include=None):
    "Create `get_files` partial function that searches path suffix `suf` and passes along args"
    def _inner(o, extensions=extensions, recurse=recurse, include=include): return get_files(o/suf, extensions, recurse, include)
    return _inner

image_extensions = set(k for k,v in mimetypes.types_map.items() if v.startswith('image/'))

def get_image_files(path, recurse=True, include=None):
    "Get image files in `path` recursively."
    return get_files(path, extensions=image_extensions, recurse=recurse, include=include)

def ImageGetter(suf='', recurse=True, include=None):
    "Create `get_image_files` partial function that searches path suffix `suf` and passes along `kwargs`"
    def _inner(o, recurse=recurse, include=include): return get_image_files(o/suf, recurse, include)
    return _inner

def RandomSplitter(valid_pct=0.2, seed=None, **kwargs):
    "Create function that splits `items` between train/val with `valid_pct` randomly."
    def _inner(o, **kwargs):
        if seed is not None: torch.manual_seed(seed)
        rand_idx = L(int(i) for i in torch.randperm(len(o)))
        cut = int(valid_pct * len(o))
        return rand_idx[cut:],rand_idx[:cut]
    return _inner

def _grandparent_idxs(items, name): return mask2idxs(Path(o).parent.parent.name == name for o in items)

def GrandparentSplitter(train_name='train', valid_name='valid'):
    "Split `items` from the grand parent folder names (`train_name` and `valid_name`)."
    def _inner(o, **kwargs):
        return _grandparent_idxs(o, train_name),_grandparent_idxs(o, valid_name)
    return _inner

def parent_label(o, **kwargs):
    "Label `item` with the parent folder name."
    return o.parent.name if isinstance(o, Path) else o.split(os.path.sep)[-1]

def RegexLabeller(pat):
    "Label `item` with regex `pat`."
    pat = re.compile(pat)
    def _inner(o, **kwargs):
        res = pat.search(str(o))
        assert res,f'Failed to find "{pat}" in "{o}"'
        return res.group(1)
    return _inner

def show_image(im, ax=None, figsize=None, title=None, ctx=None, **kwargs):
    "Show a PIL image on `ax`."
    ax = ifnone(ax,ctx)
    if ax is None: _,ax = plt.subplots(figsize=figsize)
    # Handle pytorch axis order
    if isinstance(im,Tensor):
        im = to_cpu(im)
        if im.shape[0]<5: im=im.permute(1,2,0)
    elif not isinstance(im,np.ndarray): im=array(im)
    # Handle 1-channel images
    if im.shape[-1]==1: im=im[...,0]
    ax.imshow(im, **kwargs)
    if title is not None: ax.set_title(title)
    ax.axis('off')
    return ax

def show_titled_image(o, **kwargs):
    "Call `show_image` destructuring `o` to `(img,title)`"
    show_image(o[0], title=str(o[1]), **kwargs)

def show_image_batch(b, show=show_titled_image, items=9, cols=3, figsize=None, **kwargs):
    "Display batch `b` in a grid of size `items` with `cols` width"
    rows = (items+cols-1) // cols
    if figsize is None: figsize = (cols*3, rows*3)
    fig,axs = plt.subplots(rows, cols, figsize=figsize)
    for *o,ax in zip(*to_cpu(b), axs.flatten()): show(o, ax=ax, **kwargs)

class TensorImage():
    @staticmethod
    def show(o, ctx=None, **kwargs): return show_image(to_cpu(o), ctx=ctx, **kwargs)

class Categorize(Transform):
    "Reversible transform of category string to `vocab` id"
    order,state_args=1,'vocab'
    def __init__(self, vocab=None, subset_idx=None):
        self.vocab,self.subset_idx = vocab,subset_idx
        self.o2i = None if vocab is None else {v:k for k,v in enumerate(vocab)}

    def setup(self, dsrc):
        if not dsrc: return
        dsrc = dsrc.train if self.subset_idx is None else dsrc.subset(self.subset_idx)
        self.vocab,self.o2i = uniqueify(dsrc, sort=True, bidir=True)

    def encodes(self, o): return self.o2i[o]
    def decodes(self, o): return self.vocab[o]

class String():
    @staticmethod
    def show(o, ctx=None, **kwargs): return show_title(str(o), ctx=ctx)

def mk_string(t)->String: return t

def _DataLoader__getattr(self,k):
    try: return getattr(self.dataset, k)
    except AttributeError: raise AttributeError(k) from None
DataLoader.__getattr__ = _DataLoader__getattr

def get_samples(b, max_rows):
    if isinstance(b, Tensor): return b[:max_rows]
    return zip(*L(get_samples(b_, max_rows) if not isinstance(b,Tensor) else b_[:max_rows] for b_ in b))

@docs
class TfmdDL(GetAttr):
    "Transformed `DataLoader` using a `Pipeline` of `tfm`"
    _xtra = 'batch_size num_workers dataset sampler pin_memory'.split()

    def __init__(self, dataset, tfms=None, bs=16, shuffle=False,
                 sampler=None, batch_sampler=None, num_workers=1, **kwargs):
        self.dl = DataLoader(dataset, bs, shuffle, sampler, batch_sampler, num_workers=num_workers)
        if hasattr(dataset, 'tuple_tfms'): t = dataset.tuple_tfms.final_t
        elif hasattr(dataset, 'tfms'):     t = dataset.tfms.final_t
        else:                              t = None
        self.default,self.tfms = self.dl,Pipeline(tfms, t=t)
        for k,v in kwargs.items(): setattr(self,k,v)
        self.tfms.setup(self)

    def __len__(self): return len(self.dl)
    def __iter__(self): return (self.tfms(b, filt=getattr(self.dataset, 'filt', None)) for b in self.dl)
    def one_batch(self): return next(iter(self))
    def decode(self, b):
        return getattr(self.dataset,'decode_batch',noop)(self.tfms.decode(b, filt=getattr(self.dataset, 'filt', None)))

    def show_batch(self, b=None, max_rows=1000, ctxs=None, **kwargs):
        "Show `b` (defaults to `one_batch`), a list of lists of pipeline outputs (i.e. output of a `DataLoader`)"
        if b is None: b=self.one_batch()
        b = self.tfms.decode(b, filt=getattr(self.dataset, 'filt', None))
        if ctxs is None: ctxs = [None] * len(b[0] if is_iter(b[0]) else b)
        for o,ctx in zip(get_samples(b, max_rows),ctxs): self.dataset.show(o, ctx=ctx)

    _docs = dict(decode="Decode `b` using `ds_tfm` and `tfm`",
                 show_batch="Show each item of `b`",
                 one_batch="Grab first batch of `dl`")

@docs
class Cuda(Transform):
    "Move batch to `device` (defaults to `defaults.device`)"
    def __init__(self,device=defaults.device): self.device=device
    def encodes(self, b): return to_device(b, self.device)
    def decodes(self, b): return to_cpu(b)

    _docs=dict(encodes="Move batch to `device`", decodes="Return batch to CPU")

class TensorMask(TensorImage): pass

@docs
class ByteToFloatTensor(Transform):
    "Transform image to float tensor, optionally dividing by 255 (e.g. for images)."
    order=20 #Need to run after CUDA if on the GPU
    def __init__(self, div=True, div_mask=False): self.div,self.div_mask = div,div_mask
    def encodes(self, o:TensorImage): return o.float().div_(255.) if self.div else o.float()
    def decodes(self, o:TensorImage): return o.clamp(0., 1.) if self.div else o
    def encodes(self, o:TensorMask): return o.div_(255.).long() if self.div_mask else o.long()
    def decodes(self, o:TensorMask): return o

    _docs=dict(encodes="Convert items matching `mask` to float and optionally divide by 255",
               decodes="Clamp to (0,1) items matching `mask`")

@docs
class Normalize(Transform):
    "Normalize/denorm batch of `TensorImage`"
    order=99
    def __init__(self, mean, std): self.mean,self.std = mean,std
    def encodes(self, x:TensorImage): return (x-self.mean) / self.std
    def decodes(self, x:TensorImage): return (x*self.std ) + self.mean

    _docs=dict(encodes="Normalize batch", decodes="Denormalize batch")

@docs
class DataBunch(GetAttr):
    "Basic wrapper around several `DataLoader`s."
    _xtra = 'one_batch show_batch dataset'.split()

    def __init__(self, *dls): self.dls,self.default = dls,dls[0]
    def __getitem__(self, i): return self.dls[i]

    train_dl,valid_dl = add_props(lambda i,x: x[i])
    train_ds,valid_ds = add_props(lambda i,x: x[i].dataset)

    _docs=dict(__getitem__="Retrieve `DataLoader` at `i` (`0` is training, `1` is validation)",
              train_dl="Training `DataLoader`",
              valid_dl="Validation `DataLoader`",
              train_ds="Training `Dataset`",
              valid_ds="Validation `Dataset`")