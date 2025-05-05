% Data
brokers = {'Mosquitto','EMQx','Hive','Nano','ActiveMQ','RabbitMQ','VerneMQ'};
delay = [0.0041, 0.0059, 0.0062, 0.006, 0.006, 0.0063, 0.0056];
jitter = [0.0107, 0.0072, 0.0057, 0.006, 0.006, 0.0053, 0.0073];

% Grouped data matrix
data = [delay; jitter]';

x = 1:numel(brokers);

% Create figure
figure('Position',[100 100 900 500]);

% Plot grouped bar chart
hb = bar(x, data, 'grouped');
hb(1).FaceColor = [0 0.4470 0.7410];    % blue for Delay
hb(2).FaceColor = [0.8500 0.3250 0.0980]; % orange for Jitter

% Labels and ticks
set(gca, 'XTick', x, 'XTickLabel', brokers)
xtickangle(45)
ylabel('Time (s)')
title('Delay and Jitter per Broker')

% Legend
legend({'Delay', 'Jitter'}, 'Location', 'northwest')

grid on
box on
