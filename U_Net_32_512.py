from keras.models import Model
from keras.layers import Input, Conv2D, MaxPooling2D, UpSampling2D, concatenate, Conv2DTranspose, BatchNormalization, Dropout, Lambda
from keras.optimizers import Adam
from keras.layers import Activation, MaxPool2D, Concatenate
import os
import numpy as np
from keras.optimizers import Adam
import tensorflow as tf
from keras.callbacks import ModelCheckpoint, CSVLogger

#This Code is a U-Net model with 16 starting layers and 512 layers as bridge layer.
#The model takes in rgb input and the output is binary classified image.
def conv_block(input, num_filters):
    x = Conv2D(num_filters, 3, padding="same")(input)
    x = BatchNormalization()(x)   #Not in the original network.
    x = Activation("relu")(x)

    x = Conv2D(num_filters, 3, padding="same")(x)
    x = BatchNormalization()(x)  #Not in the original network
    x = Activation("relu")(x)

    return x

#Encoder block: Conv block followed by maxpooling


def encoder_block(input, num_filters):
    x = conv_block(input, num_filters)
    p = MaxPool2D((2, 2))(x)
    return x, p

#Decoder block
#skip features gets input from encoder for concatenation

def decoder_block(input, skip_features, num_filters):
    x = Conv2DTranspose(num_filters, (2, 2), strides=2, padding="same")(input)
    x = Concatenate()([x, skip_features])
    x = conv_block(x, num_filters)
    return x

#Build Unet using the blocks
def build_unet(input_shape):
    inputs = Input(input_shape)

    s1, p1 = encoder_block(inputs, 32)
    s2, p2 = encoder_block(p1, 64)
    s3, p3 = encoder_block(p2, 128)
    s4, p4 = encoder_block(p3, 256)

    b1 = conv_block(p4, 512) #Bridge

    d1 = decoder_block(b1, s4, 256)
    d2 = decoder_block(d1, s3, 128)
    d3 = decoder_block(d2, s2, 64)
    d4 = decoder_block(d3, s1, 32)

    outputs = Conv2D(1, 1, padding="same", activation="sigmoid")(d4)
    model = Model(inputs, outputs, name="U-Net")
    return model

seed=24
batch_size= 8
from keras.preprocessing.image import ImageDataGenerator

img_data_gen_args = dict(rescale = 1/255.)

mask_data_gen_args = dict(rescale = 1/255.)

#This part of the code is for reading the input data directly from the hard drive.
image_data_generator = ImageDataGenerator(**img_data_gen_args)
image_generator = image_data_generator.flow_from_directory('#Train Images Path#',
                                                           seed=seed,
                                                           target_size=(512, 512),
                                                           batch_size=batch_size,
                                                           class_mode=None)

mask_data_generator = ImageDataGenerator(**mask_data_gen_args)
mask_generator = mask_data_generator.flow_from_directory('#Train Masks Path#',
                                                         seed=seed,
                                                         target_size=(512, 512),
                                                         batch_size=batch_size,
                                                         color_mode = 'grayscale',
                                                         class_mode=None)

valid_img_generator = image_data_generator.flow_from_directory('#validation Images Path#',
                                                               seed=seed,
                                                               target_size=(512, 512),
                                                               batch_size=batch_size,
                                                               class_mode=None)
valid_mask_generator = mask_data_generator.flow_from_directory('#validation Masks Path#',
                                                               seed=seed,
                                                               target_size=(512, 512),
                                                               batch_size=batch_size,
                                                               color_mode = 'grayscale',
                                                               class_mode=None)

train_generator = zip(image_generator, mask_generator)
val_generator = zip(valid_img_generator, valid_mask_generator)

x = image_generator.next()
y = mask_generator.next()

#Defining all the metrics that we want to abserve
from keras import backend as K
def IoU(y_true, y_pred, smooth=100):
    intersection = K.sum(K.sum(K.abs(y_true * y_pred), axis=-1))
    sum_ = K.sum(K.sum(K.abs(y_true) + K.abs(y_pred), axis=-1))
    jac = (intersection + smooth) / (sum_ - intersection + smooth)
    return (jac) * smooth

def F1_Score(y_pred, y_true):
    intersection = K.sum(K.sum(K.abs(y_true * y_pred), axis=-1))
    union = K.sum(K.sum(K.abs(y_true) + K.abs(y_pred), axis=-1))
    return 2*intersection / union

def recall(y_true, y_pred):
    true_positives = K.sum(K.round(K.clip(y_true * y_pred, 0, 1)))
    possible_positives = K.sum(K.round(K.clip(y_true, 0, 1)))
    recall = true_positives / (possible_positives + K.epsilon())
    return recall

def precision(y_true, y_pred):
    true_positives = K.sum(K.round(K.clip(y_true * y_pred, 0, 1)))
    predicted_positives = K.sum(K.round(K.clip(y_pred, 0, 1)))
    precision = true_positives / (predicted_positives + K.epsilon())
    return precision

def overall_accuracy(y_true, y_pred):
    true_positives = K.sum(K.round(K.clip(y_true * y_pred, 0, 1)))
    total_samples = K.sum(K.round(K.clip(y_true + y_pred, 0, 1)))
    acc = true_positives / (total_samples + K.epsilon())
    return acc

IMG_HEIGHT = x.shape[1]
IMG_WIDTH  = x.shape[2]
IMG_CHANNELS = x.shape[3]


input_shape = (IMG_HEIGHT, IMG_WIDTH, IMG_CHANNELS)

model = build_unet(input_shape)
#Loss Function = Binary Cross Entropy (Because this code is for binanry classification)

model.compile(optimizer=Adam(learning_rate = 1e-4), loss='binary_crossentropy', metrics=['accuracy',IoU,recall,precision,overall_accuracy])

filepath = "#Outputfile path#-{epoch:03d}-{val_loss:.3f}.hdf5"
checkpoint = ModelCheckpoint(filepath, monitor='val_loss', verbose=1, save_best_only=False, save_freq="epoch", mode='min')
log_csv = CSVLogger('#Outputfile path#/LogFile/Model_UNet_32_512_Log.csv', separator=',', append=False);
callbacks_list = [checkpoint, log_csv]

#model.summary()

num_train_imgs = len(os.listdir('#Train Images Path#'))
num_val_images = len(os.listdir('#Validation Images Path#'))

train_steps_per_epoch = num_train_imgs //batch_size
val_steps_per_epoch = num_val_images // batch_size

history = model.fit_generator(train_generator, validation_data=val_generator,steps_per_epoch=train_steps_per_epoch,validation_steps=val_steps_per_epoch, epochs=150, callbacks=callbacks_list)
