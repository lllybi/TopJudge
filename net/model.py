import torch
import torch.nn as nn
from torch.autograd import Variable
from torch.utils.data import DataLoader
import torch.optim as optim
import os

from utils import calc_accuracy, gen_result, get_num_classes


class CNN(nn.Module):
    def __init__(self, config):
        super(CNN, self).__init__()

        self.convs = []

        for a in range(config.getint("net", "min_gram"), config.getint("net", "max_gram") + 1):
            self.convs.append(nn.Conv2d(1, config.getint("net", "filters"), (a, config.getint("data", "vec_size"))))

        features = (config.getint("net", "max_gram") - config.getint("net", "min_gram") + 1) * config.getint("net",
                                                                                                             "filters")
        self.outfc = []
        task_name = config.get("data", "type_of_label").replace(" ", "").split(",")
        for x in task_name:
            self.outfc.append(nn.Linear(
                features, get_num_classes(x)
            ))

        self.midfc = []
        for x in task_name:
            self.midfc.append(nn.Linear(features, features))

        self.dropout = nn.Dropout(config.getfloat("train", "dropout"))
        self.convs = nn.ModuleList(self.convs)
        self.outfc = nn.ModuleList(self.outfc)
        self.midfc = nn.ModuleList(self.midfc)

    def init_hidden(self, config, usegpu):
        return None

    def forward(self, x, doc_len, config):
        fc_input = []
        for conv in self.convs:
            fc_input.append(self.dropout(torch.max(conv(x), dim=2, keepdim=True)[0]))

        features = (config.getint("net", "max_gram") - config.getint("net", "min_gram") + 1) * config.getint("net",
                                                                                                             "filters")

        fc_input = torch.cat(fc_input, dim=1).view(-1, features)

        outputs = []
        now_cnt = 0
        for fc in self.outfc:
            if config.getboolean("net", "more_fc"):
                outputs.append(fc(self.midfc[now_cnt](fc_input)))
            else:
                outputs.append(fc(fc_input))
            now_cnt += 1

        return outputs


class LSTM(nn.Module):
    def __init__(self, config, usegpu):
        super(LSTM, self).__init__()

        self.data_size = config.getint("data", "vec_size")
        self.hidden_dim = config.getint("net", "hidden_size")

        self.lstm = nn.LSTM(self.data_size, self.hidden_dim, batch_first=True)

        self.outfc = []
        task_name = config.get("data", "type_of_label").replace(" ", "").split(",")
        for x in task_name:
            self.outfc.append(nn.Linear(
                self.hidden_dim, get_num_classes(x)
            ))

        self.midfc = []
        for x in task_name:
            self.midfc.append(nn.Linear(self.hidden_dim, self.hidden_dim))

        self.dropout = nn.Dropout(config.getfloat("train", "dropout"))
        self.outfc = nn.ModuleList(self.outfc)
        self.hidden = self.init_hidden(config, usegpu)
        self.midfc = nn.ModuleList(self.midfc)

    def init_hidden(self, config, usegpu):
        if torch.cuda.is_available() and usegpu:
            return (
                torch.autograd.Variable(torch.zeros(1, config.getint("data", "batch_size"), self.hidden_dim).cuda()),
                torch.autograd.Variable(torch.zeros(1, config.getint("data", "batch_size"), self.hidden_dim).cuda()))
        else:
            return (torch.autograd.Variable(torch.zeros(1, config.getint("data", "batch_size"), self.hidden_dim)),
                    torch.autograd.Variable(torch.zeros(1, config.getint("data", "batch_size"), self.hidden_dim)))

    def forward(self, x, doc_len, config):

        x = x.view(config.getint("data", "batch_size"), config.getint("data", "pad_length"),
                   config.getint("data", "vec_size"))

        lstm_out, self.hidden = self.lstm(x, self.hidden)
        lstm_out = self.dropout(lstm_out)

        outv = []
        for a in range(0, len(doc_len)):
            outv.append(lstm_out[a][doc_len[a] - 1])
        lstm_out = torch.cat(outv)

        outputs = []
        now_cnt = 0
        for fc in self.outfc:
            if config.getboolean("net", "more_fc"):
                outputs.append(fc(self.midfc[now_cnt](lstm_out)))
            else:
                outputs.append(fc(lstm_out))
            now_cnt += 1

        return outputs


class CNN_FINAL(nn.Module):
    def __init__(self, config):
        super(CNN, self).__init__()

        self.convs = []

        for a in range(config.getint("net", "min_gram"), config.getint("net", "max_gram") + 1):
            self.convs.append(nn.Conv2d(1, config.getint("net", "filters"), (a, config.getint("data", "vec_size"))))

        features = (config.getint("net", "max_gram") - config.getint("net", "min_gram") + 1) * config.getint("net",
                                                                                                             "filters")
        self.outfc = []
        task_name = config.get("data", "type_of_label").replace(" ", "").split(",")
        for x in task_name:
            self.outfc.append(nn.Linear(
                features, get_num_classes(x)
            ))

        self.midfc = []
        for x in task_name:
            self.midfc.append(nn.Linear(features, features))

        self.dropout = nn.Dropout(config.getfloat("train", "dropout"))
        self.convs = nn.ModuleList(self.convs)
        self.outfc = nn.ModuleList(self.outfc)
        self.midfc = nn.ModuleList(self.midfc)

    def init_hidden(self, config, usegpu):
        return None

    def forward(self, x, doc_len, config):
        fc_input = []
        for conv in self.convs:
            fc_input.append(self.dropout(torch.max(conv(x), dim=2, keepdim=True)[0]))

        features = (config.getint("net", "max_gram") - config.getint("net", "min_gram") + 1) * config.getint("net",
                                                                                                             "filters")

        fc_input = torch.cat(fc_input, dim=1).view(-1, features)

        outputs = []
        now_cnt = 0
        for fc in self.outfc:
            if config.getboolean("net", "more_fc"):
                outputs.append(fc(self.midfc[now_cnt](fc_input)))
            else:
                outputs.append(fc(fc_input))
            now_cnt += 1

        return outputs


def test(net, test_dataset, usegpu, config, epoch):
    net.eval()
    running_acc = []
    task_name = config.get("data", "type_of_label").replace(" ", "").split(",")
    batch_size = config.getint("data", "batch_size")
    if not (os.path.exists(config.get("train", "test_path"))):
        os.makedirs(config.get("train", "test_path"))
    test_result_path = os.path.join(config.get("train", "test_path"), str(epoch))
    for a in range(0, len(task_name)):
        running_acc.append([])
        for b in range(0, get_num_classes(task_name[a])):
            running_acc[a].append({"TP": 0, "FP": 0, "FN": 0})
            running_acc[a][-1]["list"] = []
            for c in range(0, get_num_classes(task_name[a])):
                running_acc[a][-1]["list"].append(0)

    test_data_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False, drop_last=True, num_workers=1)
    for idx, data in enumerate(test_data_loader):
        inputs, doc_len, labels = data

        if isinstance(net, LSTM):
            net.hidden = net.init_hidden(config, usegpu)

        if torch.cuda.is_available() and usegpu:
            inputs, doc_len, labels = Variable(inputs.cuda()), Variable(doc_len.cuda()), Variable(labels.cuda())
        else:
            inputs, doc_len, labels = Variable(inputs), Variable(doc_len), Variable(labels)

        outputs = net.forward(inputs, doc_len, config)
        for a in range(0, len(task_name)):
            running_acc[a] = calc_accuracy(outputs[a], labels.transpose(0, 1)[a], running_acc[a])
    net.train()

    print('Test result:')
    for a in range(0, len(task_name)):
        print("%s result:" % task_name[a])
        try:
            gen_result(running_acc[a], True, file_path=test_result_path + "-" + task_name[a])
        except Exception as e:
            pass
    print("")


def train(net, train_dataset, test_dataset, usegpu, config):
    epoch = config.getint("train", "epoch")
    batch_size = config.getint("data", "batch_size")
    learning_rate = config.getfloat("train", "learning_rate")
    momemtum = config.getfloat("train", "momentum")
    shuffle = config.getboolean("data", "shuffle")

    output_time = config.getint("debug", "output_time")
    test_time = config.getint("debug", "test_time")
    task_name = config.get("data", "type_of_label").replace(" ", "").split(",")
    optimizer_type = config.get("train", "optimizer")

    model_path = config.get("train", "model_path")

    criterion = nn.CrossEntropyLoss()
    if optimizer_type == "adam":
        optimizer = optim.Adam(net.parameters(), lr=learning_rate, weight_decay=1e-3)
    elif optimizer_type == "sgd":
        optimizer = optim.SGD(net.parameters(), lr=learning_rate, momentum=momemtum)
    else:
        gg

    total_loss = []

    print("Training begin")
    net.train()
    first = True

    for epoch_num in range(0, epoch):
        running_loss = 0
        running_acc = []
        for a in range(0, len(task_name)):
            running_acc.append([])
            for b in range(0, get_num_classes(task_name[a])):
                running_acc[a].append({"TP": 0, "FP": 0, "FN": 0})
                running_acc[a][-1]["list"] = []
                for c in range(0, get_num_classes(task_name[a])):
                    running_acc[a][-1]["list"].append(0)

        cnt = 0
        train_data_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=shuffle, drop_last=True,
                                       num_workers=1)
        for idx, data in enumerate(train_data_loader):
            cnt += 1
            inputs, doc_len, labels = data
            if torch.cuda.is_available() and usegpu:
                inputs, doc_len, labels = Variable(inputs.cuda()), Variable(doc_len.cuda()), Variable(labels.cuda())
            else:
                inputs, doc_len, labels = Variable(inputs), Variable(doc_len), Variable(labels)

            net.hidden = net.init_hidden(config, usegpu)
            optimizer.zero_grad()

            outputs = net.forward(inputs, doc_len, config)
            losses = []
            for a in range(0, len(task_name)):
                losses.append(criterion(outputs[a], labels.transpose(0, 1)[a]))
                running_acc[a] = calc_accuracy(outputs[a], labels.transpose(0, 1)[a], running_acc[a])
            loss = torch.sum(torch.stack(losses))

            loss.backward()
            optimizer.step()

            running_loss += loss.data[0]

            if cnt % output_time == 0:
                print('[%d, %5d, %5d] loss: %.3f' %
                      (epoch_num + 1, cnt, idx + 1, running_loss / output_time))
                for a in range(0, len(task_name)):
                    print("%s result:" % task_name[a])
                    gen_result(running_acc[a])
                print("")

                total_loss.append(running_loss / output_time)
                running_loss = 0.0
                running_acc = []
                for a in range(0, len(task_name)):
                    running_acc.append([])
                    for b in range(0, get_num_classes(task_name[a])):
                        running_acc[a].append({"TP": 0, "FP": 0, "FN": 0})
                        running_acc[a][-1]["list"] = []
                        for c in range(0, get_num_classes(task_name[a])):
                            running_acc[a][-1]["list"].append(0)

        test(net, test_dataset, usegpu, config, epoch_num + 1)
        if not (os.path.exists(model_path)):
            os.makedirs(model_path)
        torch.save(net.state_dict(), os.path.join(model_path, "model-%d.pkl" % (epoch_num + 1)))

    print("Training done")

    test(net, test_dataset, usegpu, config, 0)
    torch.save(net.state_dict(), os.path.join(model_path, "model-0.pkl"))

    return net


def test_file(net, test_dataset, usegpu, config, epoch):
    net.eval()
    running_acc = []
    task_name = config.get("data", "type_of_label").replace(" ", "").split(",")
    if not (os.path.exists(config.get("train", "test_path"))):
        os.makedirs(config.get("train", "test_path"))
    test_result_path = os.path.join(config.get("train", "test_path"), str(epoch))
    for a in range(0, len(task_name)):
        running_acc.append([])
        for b in range(0, get_num_classes(task_name[a])):
            running_acc[a].append({"TP": 0, "FP": 0, "FN": 0})
            running_acc[a][-1]["list"] = []
            for c in range(0, get_num_classes(task_name[a])):
                running_acc[a][-1]["list"].append(0)

    while True:
        data = test_dataset.fetch_data(config)
        if data is None:
            break

        inputs, doc_len, labels = data

        if isinstance(net, LSTM):
            net.hidden = net.init_hidden(config, usegpu)

        if torch.cuda.is_available() and usegpu:
            inputs, doc_len, labels = Variable(inputs.cuda()), Variable(doc_len.cuda()), Variable(labels.cuda())
        else:
            inputs, doc_len, labels = Variable(inputs), Variable(doc_len), Variable(labels)

        outputs = net.forward(inputs, doc_len, config)
        for a in range(0, len(task_name)):
            running_acc[a] = calc_accuracy(outputs[a], labels.transpose(0, 1)[a], running_acc[a])

    net.train()

    print('Test result:')
    for a in range(0, len(task_name)):
        print("%s result:" % task_name[a])
        try:
            gen_result(running_acc[a], True, file_path=test_result_path + "-" + task_name[a])
        except Exception as e:
            pass
    print("")


def train_file(net, train_dataset, test_dataset, usegpu, config):
    epoch = config.getint("train", "epoch")
    batch_size = config.getint("data", "batch_size")
    learning_rate = config.getfloat("train", "learning_rate")
    momemtum = config.getfloat("train", "momentum")
    shuffle = config.getboolean("data", "shuffle")

    output_time = config.getint("debug", "output_time")
    test_time = config.getint("debug", "test_time")
    task_name = config.get("data", "type_of_label").replace(" ", "").split(",")
    optimizer_type = config.get("train", "optimizer")

    model_path = config.get("train", "model_path")

    criterion = nn.CrossEntropyLoss()
    if optimizer_type == "adam":
        optimizer = optim.Adam(net.parameters(), lr=learning_rate, weight_decay=1e-3)
    elif optimizer_type == "sgd":
        optimizer = optim.SGD(net.parameters(), lr=learning_rate, momentum=momemtum)
    else:
        gg

    total_loss = []
    first = True

    print("Training begin")
    for epoch_num in range(0, epoch):
        running_loss = 0
        running_acc = []
        for a in range(0, len(task_name)):
            running_acc.append([])
            for b in range(0, get_num_classes(task_name[a])):
                running_acc[a].append({"TP": 0, "FP": 0, "FN": 0})
                running_acc[a][-1]["list"] = []
                for c in range(0, get_num_classes(task_name[a])):
                    running_acc[a][-1]["list"].append(0)

        cnt = 0
        idx = 0
        while True:
            data = train_dataset.fetch_data(config)
            if data is None:
                break
            idx += batch_size
            cnt += 1

            inputs, doc_len, labels = data
            if torch.cuda.is_available() and usegpu:
                inputs, doc_len, labels = Variable(inputs.cuda()), Variable(doc_len.cuda()), Variable(labels.cuda())
            else:
                inputs, doc_len, labels = Variable(inputs), Variable(doc_len), Variable(labels)

            net.hidden = net.init_hidden(config, usegpu)
            optimizer.zero_grad()

            outputs = net.forward(inputs, doc_len, config)
            loss = 0
            for a in range(0, len(task_name)):
                loss = loss + criterion(outputs[a], labels.transpose(0, 1)[a])
                running_acc[a] = calc_accuracy(outputs[a], labels.transpose(0, 1)[a], running_acc[a])

            if first:
                loss.backward(retain_graph=True)
                first = False
            else:
                loss.backward()

            optimizer.step()

            running_loss += loss.data[0]

            if cnt % output_time == 0:
                print('[%d, %5d, %5d] loss: %.3f' %
                      (epoch_num + 1, cnt, idx + 1, running_loss / output_time))
                for a in range(0, len(task_name)):
                    print("%s result:" % task_name[a])
                    gen_result(running_acc[a])
                print("")

                total_loss.append(running_loss / output_time)
                running_loss = 0.0
                running_acc = []
                for a in range(0, len(task_name)):
                    running_acc.append([])
                    for b in range(0, get_num_classes(task_name[a])):
                        running_acc[a].append({"TP": 0, "FP": 0, "FN": 0})
                        running_acc[a][-1]["list"] = []
                        for c in range(0, get_num_classes(task_name[a])):
                            running_acc[a][-1]["list"].append(0)

        test_file(net, test_dataset, usegpu, config, epoch_num + 1)
        if not (os.path.exists(model_path)):
            os.makedirs(model_path)
        torch.save(net.state_dict(), os.path.join(model_path, "model-%d.pkl" % (epoch_num + 1)))

    print("Training done")

    test_file(net, test_dataset, usegpu, config, 0)
    torch.save(net.state_dict(), os.path.join(model_path, "model-0.pkl"))
