% Data in seconds
brokers = {'Mosquitto','EMQx','Hive','Nano','ActiveMQ','RabbitMQ','VerneMQ'};
max_s = [0.0339, 0.0377, 0.0335, 0.0399, 0.0367, 0.0388, 0.0375];
min_s = [0.0004, 0.0004, 0.0004, 0.0004, 0.0004, 0.0004, 0.0004];
avg_s = [0.016625, 0.0072, 0.0057, 0.006, 0.006, 0.0053, 0.0073];

% Convert to milliseconds
max_ms = max_s * 1000;
min_ms = min_s * 1000;
avg_ms = avg_s * 1000;

% Grouped data
data_ms = [max_ms; min_ms; avg_ms]';

% Create figure
figure('Position',[100 100 800 500]);

% Plot grouped bar chart
hb = bar(data_ms, 'grouped');
hb(1).FaceColor = [0 0.4470 0.7410];    % blue for Max
hb(2).FaceColor = [0.8500 0.3250 0.0980]; % orange for Min
hb(3).FaceColor = [0.9290 0.6940 0.1250]; % yellow for Avg

% Labels and ticks
set(gca, 'XTickLabel', brokers)
xtickangle(45)
ylabel('Delay (ms)')
title('Max, Min, Avg Delays (in ms) for Each Broker')
legend({'Max','Min','Avg'}, 'Location','northwest')

grid on
box on
