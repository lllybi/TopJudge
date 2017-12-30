import configparser
import argparse
import os
import pdb
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--config', '-c')
parser.add_argument('--gpu', '-g')
args = parser.parse_args()

configFilePath = args.config
if configFilePath is None:
    print("python *.py\t--config/-c\tconfigfile")
usegpu = True
# if args.use is None:
#    print("python *.py\t--use/-u\tcpu/gpu")
if args.gpu is None:
    usegpu = False
else:
    usegpu = True
    os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu

config = configparser.RawConfigParser()
config.read(configFilePath)

import torch
import torch.nn as nn
from torch.autograd import Variable
import torch.nn.functional as F
import math
import time
from torch.utils.data import DataLoader
import torch.optim as optim

from file_reader_gzp import init_dataset, get_num_classes, get_word_num

train_dataset, test_dataset = init_dataset(config)

epoch = config.getint("train", "epoch")
batch_size = config.getint("data", "batch_size")
learning_rate = config.getfloat("train", "learning_rate")
momemtum = config.getfloat("train", "momentum")
shuffle = config.getboolean("data", "shuffle")

output_time = config.getint("debug", "output_time")
test_time = config.getint("debug", "test_time")
task_name = config.get("data", "type_of_label").replace(" ", "").split(",")
optimizer_type = config.get("train", "optimizer")

print("Building net...")


class Net(nn.Module):
    def __init__(self):
        super(Net, self).__init__()

        # self.embed = nn.Embedding(get_word_num(), config.getint("data", "vec_size"))

        self.convs = []

        for a in range(config.getint("net", "min_gram"), config.getint("net", "max_gram") + 1):
            self.convs.append(nn.Conv2d(1, config.getint("net", "filters"), (a, config.getint("data", "vec_size"))))

        features = (config.getint("net", "max_gram") - config.getint("net", "min_gram") + 1) * config.getint("net",
                                                                                                             "filters")
        # self.fc1 = nn.Linear(features, config.getint("net", "fc1_feature"))
        self.outfc = []
        for x in task_name:
            self.outfc = nn.Linear(
                features, get_num_classes(x)
            )

        # self.softmax = nn.Softmax(dim=1)
        self.dropout = nn.Dropout(config.getfloat("train", "dropout"))
        self.convs = nn.ModuleList(self.convs)
        # self.outfc = nn.ModuleList(self.outfc)

    def forward(self, x):
        # x = self.embed(x)
        # print(x)
        x = x.unsqueeze(1)
        x = [F.relu(conv(x)).squeeze(3) for conv in self.convs] #[(N,Co,W), ...]*len(Ks)


        x = [F.max_pool1d(i, i.size(2)).squeeze(2) for i in x] #[(N,Co), ...]*len(Ks)

        x = torch.cat(x, 1)
        x = self.dropout(x) # (N,len(Ks)*Co)
        # logits = []
        # for fc in self.outfc:
            # logits.append(self.fc(x)) # (N,C)
        logits = self.outfc(x)
        return logits

        # fc_input = []
        # for conv in self.convs:
        #     fc_input.append(torch.max(conv(x), dim=2, keepdim=True)[0])

        # for x in fc_input:
        #    print(x)
        # features = (config.getint("net", "max_gram") - config.getint("net", "min_gram") + 1) * config.getint("net",
                                                                                                             # "filters")

        # fc_input = torch.cat(fc_input, dim=1).view(-1, features)

        # fc1_out = F.relu(self.fc1(fc_input))
        # outputs = []
        # for fc in self.outfc:
            # outputs.append(fc(fc_input))
            # output = self.softmax(self.fc2(fc1_out))

        # return outputs

net = Net()
if torch.cuda.is_available() and usegpu:
    net = net.cuda()
    print("gpu %d" % args.gpu)

embed = nn.Embedding(get_word_num(), config.getint("data", "vec_size"))

print("Net building done.")

criterion = nn.CrossEntropyLoss()
if optimizer_type == "adam":
    optimizer = optim.Adam(net.parameters(), lr=learning_rate, weight_decay=config.getfloat("train", "l2_nor"))
elif optimizer_type == "sgd":
    optimizer = optim.SGD(net.parameters(), lr=learning_rate, momentum=momemtum, weight_decay=config.getfloat("train", "l2_nor"))
else:
    gg


# def calc_accuracy(outputs, labels):
#     v1 = int((outputs.max(dim=1)[1].eq(labels)).sum().data.cpu().numpy())
#     v2 = 0
#     for a in range(0, len(labels)):
#         nowl = outputs[a].max(dim=0)[1]
#         v2 += int(torch.eq(nowl, labels[a]).data.cpu().numpy())

#         # if torch.eq(nowl,labels[a]) == 1:
#         #    v2 += 1
#     v3 = len(labels)
#     if v1 != v2:
#         print(outputs.max(dim=1))
#         print(labels)
#         gg
#     return (v2, v3)


# def test():
#     running_acc = []
#     for a in range(0, len(task_name)):
#         running_acc.append((0, 0))

#     while True:
#         data = test_dataset.fetch_data()
#         if data is None:
#             break

#         inputs, doc_len, labels = data

#         if torch.cuda.is_available() and usegpu:
#             inputs, doc_len, labels = Variable(inputs.cuda()), Variable(doc_len.cuda()), Variable(labels.cuda())
#         else:
#             inputs, doc_len, labels = Variable(inputs), Variable(doc_len), Variable(labels)

#         outputs = net.forward(inputs)
#         for a in range(0, len(task_name)):
#             x, y = running_acc[a]
#             r, z = calc_accuracy(outputs[a], labels.transpose(0, 1)[a])
#             running_acc[a] = (x + r, y + z)

#     print('Test accuracy:')
#     for a in range(0, len(task_name)):
#         print("%s\t%.3f\t%d\t%d" % (
#             task_name[a], running_acc[a][0] / running_acc[a][1], running_acc[a][0],
#             running_acc[a][1]))
#     print("")

def eval(data_iter, model, config):
    model.eval()
    corrects, avg_loss = 0, 0
    size = 0
    while True:
        data = test_dataset.fetch_data(config)
        if data is None:
            break
        inputs, labels = data
        if torch.cuda.is_available() and usegpu:
            inputs, labels = embed(Variable(inputs)).cuda(), Variable(labels.cuda())
        else:
            inputs, labels = embed(Variable(inputs)), Variable(labels)
        logit = model(inputs)
        loss = F.cross_entropy(logit, labels, size_average=False)

        avg_loss += loss.data[0]
        corrects += (torch.max(logit, 1)
                     [1].view(labels.size()).data == labels.data).sum()
        size += batch_size

    avg_loss = avg_loss/size
    accuracy = 100.0 * corrects/size
    model.train()
    print('\nEvaluation - loss: {:.6f}  acc: {:.4f}%({}/{}) \n'.format(avg_loss, 
                                                                       accuracy, 
                                                                       corrects, 
                                                                       size))


# total_loss = []

print("Training begin")
steps = 0
net.train()
for epoch_num in range(0, epoch):
    running_loss = 0
    running_acc = []
    for a in range(0, len(task_name)):
        running_acc.append((0, 0))
    cnt = 0
    idx = 0
    while True:
        data = train_dataset.fetch_data(config)
        if data is None:
            break
        idx += batch_size
        cnt += 1

        inputs, labels = data
        # print(inputs)
        if torch.cuda.is_available() and usegpu:
            inputs, labels = embed(Variable(inputs)).cuda(), Variable(labels.cuda())
        else:
            inputs, labels = embed(Variable(inputs)), Variable(labels)
        # print(inputs)
        optimizer.zero_grad()

        outputs = net.forward(inputs)
        # for a in range(0, len(task_name)):
            # loss = loss + criterion(outputs[a], labels.transpose(0, 1)[a])
            # x, y = running_acc[a]
            # r, z = calc_accuracy(outputs[a], labels.transpose(0, 1)[a])
            # running_acc[a] = (x + r, y + z)
        # pdb.set_trace()
        # print(outputs)
        loss = F.cross_entropy(outputs, labels)
        loss.backward()
        optimizer.step()
        steps += 1
        if steps % config.getint("train", "log_interval") == 0:
            corrects = (torch.max(outputs, 1)[1].view(labels.size()).data == labels.data).sum()
            accuracy = 100.0 * corrects/batch_size
            sys.stdout.write(
                '\rBatch[{}] - loss: {:.6f}  acc: {:.4f}%({}/{})'.format(steps, 
                                                                         loss.data[0], 
                                                                         accuracy,
                                                                         corrects,
                                                                         batch_size))
        if steps % config.getint("train", "test_interval") == 0:
            eval(test_dataset, net, config)
        # if steps % args.save_interval == 0:
        #     if not os.path.isdir(args.save_dir): os.makedirs(args.save_dir)
        #     save_prefix = os.path.join(args.save_dir, 'snapshot')
        #     save_path = '{}_steps{}.pt'.format(save_prefix, steps)
        #     torch.save(model, save_path)
        # loss.backward()
        # optimizer.step()
        # # pdb.set_trace()

        # running_loss += loss.data[0]

        # if cnt % output_time == 0:
        #     print('[%d, %5d, %5d] loss: %.3f' %
        #           (epoch_num + 1, cnt, idx + 1, running_loss / output_time))
        #     print('accuracy:')
        #     # print(running_acc)
        #     for a in range(0, len(task_name)):
        #         print("%s\t%.3f\t%d\t%d" % (
        #             task_name[a] + "accuracy", running_acc[a][0] / running_acc[a][1], running_acc[a][0],
        #             running_acc[a][1]))
        #     print("")
        #     total_loss.append(running_loss / output_time)
        #     running_loss = 0.0
        #     for a in range(0, len(task_name)):
        #         running_acc[a] = (0, 0)

        # if cnt % test_time == 0:
        #     test()

print("Training done")
eval()
# test()