% Data
brokers = {'Mosquitto','EMQx','Hive','Nano','ActiveMQ','RabbitMQ','VerneMQ'};
cpu_percent = [1.1471, 7.8956, 10.6908, 4.1037, 9.5986, 5.0047, 8.4963];
mem_percent = [0.05, 3.57, 4.30, 0.06, 3.63, 2.43, 1.44];
net_rx = [96989953.5, 18965934.25, 23480247.42, 23485638.78, 23409917.75, 19246568.1, 17983216.39];
net_tx = [25690920.31, 4735995.661, 6026199.987, 6036795.047, 6004083.725, 4764633.525, 4523262.754];

x = 1:numel(brokers);

% Create figure
figure('Position',[100 100 1000 600]);

% Left Y-axis: CPU and Memory as grouped bars
yyaxis left
hb = bar(x, [cpu_percent; mem_percent].', 'grouped');
hb(1).FaceColor = [0 0.4470 0.7410];     % blue for CPU
hb(2).FaceColor = [0.8500 0.3250 0.0980]; % orange for Memory
ylabel('CPU / Memory (%)')
ylim([0, max([cpu_percent, mem_percent]) * 1.2])

% X-axis setup
set(gca, 'XTick', x, 'XTickLabel', brokers)
xtickangle(45)

% Right Y-axis: Net RX and Net TX as lines
yyaxis right
plot(x, net_rx, '-o', 'LineWidth', 2, 'Color', [0.4660 0.6740 0.1880], 'DisplayName', 'Net RX')
hold on
plot(x, net_tx, '-s', 'LineWidth', 2, 'Color', [0.4940 0.1840 0.5560], 'DisplayName', 'Net TX')
ylabel('Network Traffic (bytes)')
ylim([0, max([net_rx, net_tx]) * 1.2])

% Title and legend
title('CPU %, Memory %, Net RX, and Net TX per Broker')
legend({'CPU %', 'Memory %', 'Net RX', 'Net TX'}, 'Location', 'northwest')

grid on
box on
