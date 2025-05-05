% Data
brokers = {'Mosquitto','EMQx','Hive','Nano','ActiveMQ','RabbitMQ','VerneMQ'};
availability = [100, 100, 100, 100, 100, 100, 100]; % in %
mttr = [0, 0, 0, 0, 0, 0, 0];                      % in seconds
failure_rate = [0.01662, 0.016625, 0.016625, 0.016638, 0.016628, 0.016618, 0.016628];
reliability = [98.3380, 98.3375, 98.3375, 98.3362, 98.3372, 98.3382, 98.3372]; % in %

% Grouped data matrix
data = [availability; mttr; failure_rate; reliability]';

x = 1:numel(brokers);

% Create figure
figure('Position',[100 100 900 500]);

% Plot grouped bar chart
hb = bar(x, data, 'grouped');
hb(1).FaceColor = [0 0.4470 0.7410];     % blue for Availability
hb(2).FaceColor = [0.8500 0.3250 0.0980]; % orange for MTTR
hb(3).FaceColor = [0.9290 0.6940 0.1250]; % yellow for Failure Rate
hb(4).FaceColor = [0.4940 0.1840 0.5560]; % purple for Reliability

% Labels and ticks
set(gca, 'XTick', x, 'XTickLabel', brokers)
xtickangle(45)
ylabel('Value')
title('Availability, MTTR, Failure Rate, Reliability for Brokers')

% Legend
legend({'Availability (%)', 'MTTR (s)', 'Failure Rate', 'Reliability (%)'}, ...
       'Location', 'northwest')

grid on
box on
