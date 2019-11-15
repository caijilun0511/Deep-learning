'''
说明：采用数据集较小的dataset1数据集进行训练，了解参数的调整方法和模型的相关训练方法。
'''
import random
import sys
import time
import warnings
import os
import cv2
import tensorflow as tf
from tensorflow.python.keras import backend as K
from tensorflow.python.keras.models import *
from tensorflow.python.keras.layers import *
from tensorflow.python.keras.callbacks import TensorBoard
from tensorflow.python.keras import optimizers
import pandas as pd
import numpy as np
from sklearn.utils import shuffle

dir_data = '/home/ye/zhouhua/datasets/dataset1'
dir_seg = dir_data + "/annotations_prepped_train/"
dir_img = dir_data + "/images_prepped_train/"
VGG_Weights_path = '/home/ye/zhouhua/models/vgg16_weights_tf_dim_ordering_tf_kernels_notop.h5'

input_height, input_width = 224, 224
output_height, output_width = 224, 224
shape = (224, 224)
n_classes = 10


def give_color_to_seg_img(seg, n_classes):
    '''
    seg : (input_width,input_height,3)
    '''

    if len(seg.shape) == 3:
        seg = seg[:, :, 0]
    seg_img = np.zeros((seg.shape[0], seg.shape[1], 3)).astype('float')
    colors = sns.color_palette("hls", n_classes)

    for c in range(n_classes):
        segc = (seg == c)
        seg_img[:, :, 0] += (segc*(colors[c][0]))
        seg_img[:, :, 1] += (segc*(colors[c][1]))
        seg_img[:, :, 2] += (segc*(colors[c][2]))

    return (seg_img)


def getImageArr(path, width, height):
    img = cv2.imread(path, 1)
    img = np.float32(cv2.resize(img, (width, height))) / 127.5 - 1
    return img


def getSegmentationArr(path, nClasses,  width, height):

    seg_labels = np.zeros((height, width, nClasses))
    img = cv2.imread(path, 1)
    img = cv2.resize(img, (width, height))
    img = img[:, :, 0]

    for c in range(nClasses):
        seg_labels[:, :, c] = (img == c).astype(int)
    ##seg_labels = np.reshape(seg_labels, ( width*height,nClasses  ))
    return seg_labels


def readImgaeAndSeg():
    images = os.listdir(dir_img)
    images.sort()
    segmentations = os.listdir(dir_seg)
    segmentations.sort()
    X = []
    Y = []
    for im, seg in zip(images, segmentations):
        X.append(getImageArr(dir_img + im, input_width, input_height))
        Y.append(getSegmentationArr(dir_seg + seg,
                                    n_classes, output_width, output_height))

    X, Y = np.array(X), np.array(Y)
    print('X.shape,Y.shape: ', X.shape, Y.shape)
    return X, Y


def GPUConfig():
    warnings.filterwarnings("ignore")
    os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    config = tf.ConfigProto()
    config.gpu_options.per_process_gpu_memory_fraction = 0.95
    config.gpu_options.visible_device_list = "1"
    K.set_session(tf.Session(config=config))
    print("python {}".format(sys.version))
    print("tensorflow version {}".format(tf.__version__))


def FCN8(nClasses,  input_height=224, input_width=224):
    # input_height and width must be devisible by 32 because maxpooling with filter size = (2,2) is operated 5 times,
    # which makes the input_height and width 2^5 = 32 times smaller
    assert input_height % 32 == 0
    assert input_width % 32 == 0
    IMAGE_ORDERING = "channels_last"

    img_input = Input(shape=(input_height, input_width, 3))  # Assume 224,224,3

    # Block 1
    x = Conv2D(64, (3, 3), activation='relu', padding='same',
               name='block1_conv1', data_format=IMAGE_ORDERING)(img_input)
    x = Conv2D(64, (3, 3), activation='relu', padding='same',
               name='block1_conv2', data_format=IMAGE_ORDERING)(x)
    x = MaxPooling2D((2, 2), strides=(2, 2), name='block1_pool',
                     data_format=IMAGE_ORDERING)(x)
    f1 = x

    # Block 2
    x = Conv2D(128, (3, 3), activation='relu', padding='same',
               name='block2_conv1', data_format=IMAGE_ORDERING)(x)
    x = Conv2D(128, (3, 3), activation='relu', padding='same',
               name='block2_conv2', data_format=IMAGE_ORDERING)(x)
    x = MaxPooling2D((2, 2), strides=(2, 2), name='block2_pool',
                     data_format=IMAGE_ORDERING)(x)
    f2 = x

    # Block 3
    x = Conv2D(256, (3, 3), activation='relu', padding='same',
               name='block3_conv1', data_format=IMAGE_ORDERING)(x)
    x = Conv2D(256, (3, 3), activation='relu', padding='same',
               name='block3_conv2', data_format=IMAGE_ORDERING)(x)
    x = Conv2D(256, (3, 3), activation='relu', padding='same',
               name='block3_conv3', data_format=IMAGE_ORDERING)(x)
    x = MaxPooling2D((2, 2), strides=(2, 2), name='block3_pool',
                     data_format=IMAGE_ORDERING)(x)
    pool3 = x

    # Block 4
    x = Conv2D(512, (3, 3), activation='relu', padding='same',
               name='block4_conv1', data_format=IMAGE_ORDERING)(x)
    x = Conv2D(512, (3, 3), activation='relu', padding='same',
               name='block4_conv2', data_format=IMAGE_ORDERING)(x)
    x = Conv2D(512, (3, 3), activation='relu', padding='same',
               name='block4_conv3', data_format=IMAGE_ORDERING)(x)
    pool4 = MaxPooling2D((2, 2), strides=(
        2, 2), name='block4_pool', data_format=IMAGE_ORDERING)(x)  # (None, 14, 14, 512)

    # Block 5
    x = Conv2D(512, (3, 3), activation='relu', padding='same',
               name='block5_conv1', data_format=IMAGE_ORDERING)(pool4)
    x = Conv2D(512, (3, 3), activation='relu', padding='same',
               name='block5_conv2', data_format=IMAGE_ORDERING)(x)
    x = Conv2D(512, (3, 3), activation='relu', padding='same',
               name='block5_conv3', data_format=IMAGE_ORDERING)(x)
    pool5 = MaxPooling2D((2, 2), strides=(
        2, 2), name='block5_pool', data_format=IMAGE_ORDERING)(x)  # (None, 7, 7, 512)

    #x = Flatten(name='flatten')(x)
    #x = Dense(4096, activation='relu', name='fc1')(x)
    # <--> o = ( Conv2D( 4096 , ( 7 , 7 ) , activation='relu' , padding='same', data_format=IMAGE_ORDERING))(o)
    # assuming that the input_height = input_width = 224 as in VGG data

    #x = Dense(4096, activation='relu', name='fc2')(x)
    # <--> o = ( Conv2D( 4096 , ( 1 , 1 ) , activation='relu' , padding='same', data_format=IMAGE_ORDERING))(o)
    # assuming that the input_height = input_width = 224 as in VGG data

    #x = Dense(1000 , activation='softmax', name='predictions')(x)
    # <--> o = ( Conv2D( nClasses ,  ( 1 , 1 ) ,kernel_initializer='he_normal' , data_format=IMAGE_ORDERING))(o)
    # assuming that the input_height = input_width = 224 as in VGG data

    vgg = Model(img_input, pool5)
    # loading VGG weights for the encoder parts of FCN8
    vgg.load_weights(VGG_Weights_path)

    n = 4096
    o = (Conv2D(n, (7, 7), activation='relu', padding='same',
                name="conv6", data_format=IMAGE_ORDERING))(pool5)
    conv7 = (Conv2D(n, (1, 1), activation='relu', padding='same',
                    name="conv7", data_format=IMAGE_ORDERING))(o)

    # 4 times upsamping for pool4 layer
    conv7_4 = Conv2DTranspose(nClasses, kernel_size=(4, 4),  strides=(
        4, 4), use_bias=False, data_format=IMAGE_ORDERING)(conv7)
    ## (None, 224, 224, 10)
    # 2 times upsampling for pool411
    pool411 = (Conv2D(nClasses, (1, 1), activation='relu', padding='same',
                      name="pool4_11", data_format=IMAGE_ORDERING))(pool4)
    pool411_2 = (Conv2DTranspose(nClasses, kernel_size=(2, 2),  strides=(
        2, 2), use_bias=False, data_format=IMAGE_ORDERING))(pool411)

    pool311 = (Conv2D(nClasses, (1, 1), activation='relu', padding='same',
                      name="pool3_11", data_format=IMAGE_ORDERING))(pool3)

    o = Add(name="add")([pool411_2, pool311, conv7_4])
    o = Conv2DTranspose(nClasses, kernel_size=(8, 8),  strides=(
        8, 8), use_bias=False, data_format=IMAGE_ORDERING)(o)
    o = (Activation('softmax'))(o)

    model = Model(img_input, o)

    return model


def splitDatasets(X, Y, train_rate=0.85):

    index_train = np.random.choice(X.shape[0], int(
        X.shape[0]*train_rate), replace=False)
    index_test = list(set(range(X.shape[0])) - set(index_train))

    X, Y = shuffle(X, Y)
    X_train, y_train = X[index_train], Y[index_train]
    X_test, y_test = X[index_test], Y[index_test]

    print(X_train.shape, y_train.shape)
    print(X_test.shape, y_test.shape)
    return (X_train, y_train), (X_test, y_test)


def IoU(Yi, y_predi):
    # mean Intersection over Union
    # Mean IoU = TP/(FN + TP + FP)

    IoUs = []
    Nclass = int(np.max(Yi)) + 1
    for c in range(Nclass):
        TP = np.sum((Yi == c) & (y_predi == c))
        FP = np.sum((Yi != c) & (y_predi == c))
        FN = np.sum((Yi == c) & (y_predi != c))
        IoU = TP/float(TP + FP + FN)
        print("class {:02.0f}: #TP={:6.0f}, #FP={:6.0f}, #FN={:5.0f}, IoU={:4.3f}".format(
            c, TP, FP, FN, IoU))
        IoUs.append(IoU)
    mIoU = np.mean(IoUs)
    print("_________________")
    print("Mean IoU: {:4.3f}".format(mIoU))


if __name__ == '__main__':
    X, Y = readImgaeAndSeg()
    (X_train, y_train), (X_test, y_test) = splitDatasets(X, Y, 0.85)
    tensorboard = TensorBoard(
        log_dir='/home/ye/zhouhua/logs/FCN/FCN-dataset1-keras-{}'.format(int(time.time())))

    model = FCN8(nClasses=n_classes,
                 input_height=224,
                 input_width=224)
    model.summary()

    sgd = optimizers.SGD(lr=1E-2, decay=5**(-4), momentum=0.9, nesterov=True)
    model.compile(loss='categorical_crossentropy',
                  optimizer=sgd,
                  metrics=['accuracy']
                  )

    hist1 = model.fit(X_train, y_train,
                      validation_data=(X_test, y_test),
                      batch_size=32, epochs=200, verbose=1,callbacks=[tensorboard])
    model.save('/home/ye/zhouhua/models/FCN-dataset1-keras.model')