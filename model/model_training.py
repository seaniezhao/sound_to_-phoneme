import torch
import torch.optim as optim
import torch.utils.data
import time
import os
import torch.nn as nn
from datetime import datetime
from torch.autograd import Variable




class ModelTrainer:
    def __init__(self,
                 model,
                 dataset,
                 device,
                 snapshot_path=None,
                 snapshot_name='snapshot',
                 snapshot_interval=1000,
                 lr=0.0005,
                 weight_decay=0):

        self.model = model
        self.dataset = dataset
        self.dataloader = None
        self.lr = lr
        self.weight_decay = weight_decay
        self.device = device

        self.snapshot_path = snapshot_path
        self.snapshot_name = snapshot_name
        self.snapshot_interval = snapshot_interval

        self.optimizer = optim.Adam(params=self.model.parameters(), lr=self.lr, weight_decay=self.weight_decay)

        self.clip = None

        self.device_count = torch.cuda.device_count()

        self.start_epoch = 0
        self.epoch = 0

        self.loss_func = nn.CrossEntropyLoss()

    def adjust_learning_rate(self):

        real_epoch = self.start_epoch + self.epoch
        lr = self.lr / (1 + 0.00001 * real_epoch)

        for param_group in self.optimizer.param_groups:
            param_group['lr'] = lr

    def train(self, batch_size=32, epochs=10):

        self.model.train()
        if self.device_count > 1:
            self.model = nn.DataParallel(self.model)
            print('multiple device using :', self.device_count)

        self.dataloader = torch.utils.data.DataLoader(self.dataset,
                                                      batch_size=batch_size,
                                                      shuffle=True,
                                                      num_workers=8,
                                                      pin_memory=False)
        step = 0
        for current_epoch in range(epochs):
            print("epoch", current_epoch)
            self.epoch = current_epoch

            self.adjust_learning_rate()
            tic = time.time()
            epoch_loss = 0
            epoch_step = 0
            for (x, target) in iter(self.dataloader):

                x = x.to(self.device)
                target = target.to(self.device)

                output = self.model(x)
                output = output.squeeze()
                loss = self.loss_func(output, target)

                self.optimizer.zero_grad()
                loss.backward()
                loss = loss.item()
                epoch_loss += loss
                epoch_step += 1
                #print('loss: ', loss)
                if self.clip is not None:
                    torch.nn.utils.clip_grad_norm(self.model.parameters(), self.clip)
                self.optimizer.step()
                step += 1

                # time step duration:
                if step == 100:
                    toc = time.time()
                    print("one training step does take approximately " + str((toc - tic) * 0.01) + " seconds)")

            self.save_model()
            toc = time.time()
            print("one epoch does take approximately " + str((toc - tic)) + " seconds)  ave_loss: " + str(epoch_loss/epoch_step))

        self.save_model()


    def load_checkpoint(self, filename):

        if os.path.isfile(filename):
            print("=> loading checkpoint '{}'".format(filename))
            checkpoint = torch.load(filename)
            self.start_epoch = checkpoint['epoch']
            self.model.load_state_dict(checkpoint['state_dict'])
            self.optimizer.load_state_dict(checkpoint['optimizer'])

            print("=> loaded checkpoint '{}' (epoch {})"
                  .format(filename, checkpoint['epoch']))
        else:
            print("=> no checkpoint found at '{}'".format(filename))

        return self.start_epoch


    def validate(self):
        self.model.eval()


        return None

    def save_model(self):
        if self.snapshot_path is None:
            return
        time_string = time.strftime("%Y-%m-%d_%H-%M-%S", time.gmtime())
        if not os.path.exists(self.snapshot_path):
            os.mkdir(self.snapshot_path)
        to_save = self.model
        if self.device_count > 1:
            to_save = self.model.module

        str_epoch = str(self.start_epoch + self.epoch)
        filename = self.snapshot_path + '/' + self.snapshot_name + '_' + str_epoch + '_' + time_string
        state = {'epoch': self.epoch + 1, 'state_dict': to_save.state_dict(),
                 'optimizer': self.optimizer.state_dict()}
        torch.save(state, filename)

        print('model saved')
