import tensorflow as tf
from .base import BaseNet


class xNN(BaseNet):
    """
    Explainable neural network (xNN).

    Parameters
    ----------
    :type input_num: int
    :param input_num: the length of input variables, excluding multi-class categorical variables.
        
    :type subnet_num: int
    :param subnet_num: the number of subnetworks.

    :type  input_dummy_num: int
    :param input_dummy_num: optional, default=0, the number of dummy variables.

    :type  subnet_layers: list
    :param subnet_layers: optional, default=(10, 6), the architecture of each subnetworks, the ith element represents the number of neurons in the ith layer.

    :type  task: string
    :param task: optional, one of {"Regression", "Classification"}, default="Regression". Only support binary classification at current version.

    :type  batch_size: int
    :param batch_size: optional, default=1000, size of minibatches for stochastic optimizers.

    :type  training_epochs: int
    :param training_epochs: optional, default=10000, maximum number of training epochs.

    :type  tune_epochs: int
    :param tune_epochs: optional, default=500, number of tuning epochs.

    :type  activation: tf object
    :param activation: optional, default=tf.tanh, activation function for the hidden layer of subnetworks. It can be any tensorflow activation function object.

    :type  lr_BP: float
    :param lr_BP: optional, default=0.001, learning rate for weight updates.

    :type  beta_threshold: float
    :param beta_threshold: optional, default=0.01, percentage threshold for pruning the subnetworks, which means the subnetworks that sum up to 95% of the total sclae will be kept.

    :type  l1_proj: float
    :param l1_proj: optional, default=0.001, the strength of L1 penalty for projection layer.

    :type  l1_subnet: float
    :param l1_subnet: optional, default=0.001, the strength of L1 penalty for scaling layer.

    :type  verbose: bool
    :param verbose: optional, default=False. If True, detailed messages will be printed.

    :type  val_ratio : float
    :param val_ratio : optional, default=0.2. The proportion of training data to set aside as validation set for early stopping. Must be between 0 and 1.

    :type  early_stop_thres: int
    :param early_stop_thres: optional, default=1000. Maximum number of epochs if no improvement occurs.

    Notes
    -----
    xNN is based on the Explainable neural network (Joel et al. 2018) with the following implementation details:
    1. Categorical variables should be first converted by one-hot encoding, and we directly link each
      of the dummy variables as a bias term to final output.
    2. The projection layer weights are initialized with univariate coefficient or combination of coefficients, 
      considering the number of subnetworks. See the projection_layer function for details. 
    3. We train the network and early stop if no improvement occurs in certain epochs. 
    4. The subnetworks whose scaling factors are close to zero are pruned for parsimony consideration.
    5. The pruned network will then be fine-tuned. 
    
    References
    ----------
    J. Vaughan, A. Sudjianto, E. Brahimi, J. Chen, and V. N. Nair, "Explainable
    neural networks based on additive index models," The RMA
    Journal, pp. 40-49, October 2018.
    """

    def __init__(self, input_num, subnet_num, input_dummy_num=0, subnet_arch=[10, 6], task="Regression",
                 activation_func=tf.tanh, batch_size=1000, training_epochs=10000, lr_bp=0.001,
                 beta_threshold=0.01, tuning_epochs=500, l1_proj=0.001, l1_subnet=0.001,
                 verbose=False, val_ratio=0.2, early_stop_thres=1000):

        super(xNN, self).__init__(input_num=input_num,
                                  input_dummy_num=input_dummy_num,
                                  subnet_num=subnet_num,
                                  subnet_arch=subnet_arch,
                                  task=task,
                                  proj_method="comb",
                                  activation_func=tf.tanh,
                                  bn_flag=False,
                                  lr_bp=lr_bp,
                                  l1_proj=l1_proj,
                                  l1_subnet=l1_subnet,
                                  smooth_lambda=0,
                                  batch_size=batch_size,
                                  training_epochs=training_epochs,
                                  tuning_epochs=tuning_epochs,
                                  beta_threshold=beta_threshold,
                                  verbose=verbose,
                                  val_ratio=val_ratio,
                                  early_stop_thres=early_stop_thres)

    @tf.function
    def train_step_init(self, inputs, labels):

        with tf.GradientTape() as tape:
            pred = self.apply(inputs, training=True)
            pred_loss = self.loss_fn(labels, pred)
            regularization_loss = tf.math.add_n(self.proj_layer.losses + self.output_layer.losses)
            total_loss = pred_loss + regularization_loss

        grads = tape.gradient(total_loss, self.trainable_weights)
        self.optimizer.apply_gradients(zip(grads, self.trainable_weights))

    @tf.function
    def train_step_finetune(self, inputs, labels):

        with tf.GradientTape() as tape:
            pred = self.apply(inputs, training=True)
            pred_loss = self.loss_fn(labels, pred)
            total_loss = pred_loss

        variables = list(set(self.trainable_weights).difference(set(self.proj_layer.weights)))
        grads = tape.gradient(total_loss, variables)
        self.optimizer.apply_gradients(zip(grads, variables))