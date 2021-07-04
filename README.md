[tf-keras-vis](https://keisen.github.io/tf-keras-vis-docs/)
===

[![Downloads](https://pepy.tech/badge/tf-keras-vis)](https://pepy.tech/project/tf-keras-vis)
[![PyPI version](https://badge.fury.io/py/tf-keras-vis.svg)](https://badge.fury.io/py/tf-keras-vis)
[![Python package](https://github.com/keisen/tf-keras-vis/actions/workflows/python-package.yml/badge.svg)](https://github.com/keisen/tf-keras-vis/actions/workflows/python-package.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)


Notes
---

We've released `v0.7.0`! In this release, the gradient calculation of ActivationMaximization is changed for the sake of fixing a critical problem. Although the calculation result are now a bit different compared to the past versions, you could avoid it by using legacy implementation as follows:

```python
# from tf_keras_vis.activation_maximization import ActivationMaximization
from tf_keras_vis.activation_maximization.legacy import ActivationMaximization
```

In addition to above, we've also fixed some problems related Regularizers. Although we newly provide `tf_keras_vis.activation_maximization.regularizers` module that includes the regularizers whose bugs are fixed, like ActivationMaximization, you could also use legacy implementation as follows:

```python
# from tf_keras_vis.activation_maximization.regularizers import Norm, TotalVariation2D 
from tf_keras_vis.utils.regularizers import Norm, TotalVariation2D
```

Please see [the release note](https://github.com/keisen/tf-keras-vis/releases/tag/v0.7.0) for details. If you face any problem related to this release, please feel free to ask us in [Issues page](https://github.com/keisen/tf-keras-vis/issues)!


Web documents
-------------

https://keisen.github.io/tf-keras-vis-docs/


Overview
---

tf-keras-vis is a visualization toolkit for debugging `tf.keras.Model` in Tensorflow2.0+.
Currently supported methods for visualization include:

* Feature Visualization
   - ActivationMaximization
* Class Activation Maps
   - [GradCAM](https://arxiv.org/pdf/1610.02391v1.pdf)
   - [GradCAM++](https://arxiv.org/pdf/1710.11063.pdf)
   - [ScoreCAM](https://arxiv.org/pdf/1910.01279.pdf)
   - [Faster-ScoreCAM](https://github.com/tabayashi0117/Score-CAM/blob/master/README.md#faster-score-cam)
* Saliency Maps
   - [Vanilla Saliency](https://arxiv.org/pdf/1312.6034.pdf)
   - [SmoothGrad](https://arxiv.org/pdf/1706.03825.pdf)

tf-keras-vis is designed to be light-weight, flexible and ease of use.
All visualizations have the features as follows:

* Support **N-dim image inputs**, that's, not only support pictures but also such as 3D images.
* Support **batch wise** processing, so, be able to efficiently process multiple input images.
* Support the model that have either **multiple inputs** or **multiple outputs**, or both.
* Support the **mixed-precision** model.

And in ActivationMaximization,

* Support Optimizers that are built to tf.keras.


Visualizations
---

### Visualizing Dense Layer

<img src='https://github.com/keisen/tf-keras-vis/raw/master/examples/images/visualize-dense-layer.png' width='600px' />

### Visualizing Convolutional Filer

<img src='https://github.com/keisen/tf-keras-vis/raw/master/examples/images/visualize-filters.png' width='600px' />

### GradCAM

<img src='https://github.com/keisen/tf-keras-vis/raw/master/examples/images/gradcam_plus_plus.png' width='600px' />

The images above are generated by `GradCAM++`.

### Saliency Map

<img src='https://github.com/keisen/tf-keras-vis/raw/master/examples/images/smoothgrad.png' width='600px' />

The images above are generated by `SmoothGrad`.


Usage
---

* ActivationMaximization (Visualizing Convolutional Filter)

```python
import tensorflow as tf
from tensorflow.keras.applications import VGG16
from matplotlib import pyplot as plt
from tf_keras_vis.activation_maximization import ActivationMaximization
from tf_keras_vis.activation_maximization.callbacks import Progress
from tf_keras_vis.activation_maximization.input_modifiers import Jitter, Rotate2D
from tf_keras_vis.activation_maximization.regularizers import TotalVariation2D, Norm
from tf_keras_vis.utils.model_modifiers import ExtractIntermediateLayer, ReplaceToLinear
from tf_keras_vis.utils.scores import CategoricalScore

# Create the visualization instance.
# All visualization classes accept a model and model-modifier, which, for example,
#     replaces the activation of last layer to linear function so on, in constructor.
activation_maximization = \
   ActivationMaximization(VGG16(),
                          model_modifier=[ExtractIntermediateLayer('block5_conv3'),
                                          ReplaceToLinear()],
                          clone=False)

# You can use Score class to specify visualizing target you want.
# And add regularizers or input-modifiers as needed.
activations = \
   activation_maximization(CategoricalScore(FILTER_INDEX),
                           steps=200,
                           input_modifiers=[Jitter(jitter=16), Rotate2D(degree=1)],
                           regularizers=[TotalVariation2D(weight=1.0),
                                         Norm(weight=0.3, p=1)],
                           optimizer=tf.keras.optimizers.RMSprop(1.0, 0.999),
                           callbacks=[Progress()])

## Since v0.6.0, calling `astype()` is NOT necessary.
# activations = activations[0].astype(np.uint8)

# Render
plt.imshow(activations[0])
```

* Gradcam++

```python
import numpy as np
from matplotlib import pyplot as plt
from matplotlib import cm
from tf_keras_vis.gradcam_plus_plus import GradcamPlusPlus
from tf_keras_vis.utils.model_modifiers import ReplaceToLinear
from tf_keras_vis.utils.scores import CategoricalScore

# Create GradCAM++ object
gradcam = GradcamPlusPlus(YOUR_MODEL_INSTANCE,
                          model_modifier=ReplaceToLinear(),
                          clone=True)

# Generate cam with GradCAM++
cam = gradcam(CategoricalScore(CATEGORICAL_INDEX),
              SEED_INPUT)

## Since v0.6.0, calling `normalize()` is NOT necessary.
# cam = normalize(cam)

plt.imshow(SEED_INPUT_IMAGE)
heatmap = np.uint8(cm.jet(cam[0])[..., :3] * 255)
plt.imshow(heatmap, cmap='jet', alpha=0.5) # overlay
```

Please see the guides below for more details:

### Getting Started Guides

* [Saliency and CAMs](https://github.com/keisen/tf-keras-vis/blob/master/examples/attentions.ipynb)
* [Visualize Dense Layer](https://github.com/keisen/tf-keras-vis/blob/master/examples/visualize_dense_layer.ipynb)
* [Visualize Convolutional Filer](https://github.com/keisen/tf-keras-vis/blob/master/examples/visualize_conv_filters.ipynb)

**[NOTE]**
If you have ever used [keras-vis](https://github.com/raghakot/keras-vis), you may feel that tf-keras-vis is similar with keras-vis.
Actually tf-keras-vis derived from keras-vis, and both provided visualization methods are almost the same.
But please notice that tf-keras-vis APIs does NOT have compatibility with keras-vis.


Requirements
---

* Python 3.6-3.9
* tensorflow>=2.0.4


Installation
---

* PyPI

```bash
$ pip install tf-keras-vis tensorflow
```

* Source (for development)

```bash
$ git clone https://github.com/keisen/tf-keras-vis.git
$ cd tf-keras-vis
$ pip install -e .[develop]
```


Use Cases
---

* [chitra](https://github.com/aniketmaurya/chitra)
   * A Deep Learning Computer Vision library for easy data loading, model building and model interpretation with GradCAM/GradCAM++.


Known Issues
---

* With InceptionV3, ActivationMaximization doesn't work well, that's, it might generate meaninglessly blur image.
* With cascading model, Gradcam and Gradcam++ don't work well, that's, it might occur some error. So we recommend to use FasterScoreCAM in this case.
* `channels-first` models and data is unsupported.


ToDo
---

* Guides
   * Visualizing multiple attention or activation images at once utilizing batch-system of model
   * Define various score functions
   * Visualizing attentions with multiple inputs models
   * Visualizing attentions with multiple outputs models
   * Advanced score functions
   * Tuning Activation Maximization
   * Visualizing attentions for N-dim image inputs
*  Publish API documentations as a website
*  We're going to add some methods such as below
   - Deep Dream
   - Style transfer
