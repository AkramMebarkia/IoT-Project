% Data
brokers = {'Mosquitto','EMQx','Hive','Nano','ActiveMQ','RabbitMQ','VerneMQ'};
e2e = [1.284286293, 0.855313878, 1.243022908, 0.869942608, 1.013806883, 1.117970241, 1.227438513];
setup = [3.018673897, 15.68590283, 3.029363155, 3.01328516, 14.02245967, 20.67635934, 22.35512932];
sub = [0.00077045, 0.001524687, 0.002347231, 0.000854492, 0.002369722, 0.005697807, 0.001174212];

x = 1:numel(brokers);

% Create figure
figure('Position',[100 100 900 500]);

% Left Y-axis: grouped bar plot
yyaxis left
hb = bar(x, [e2e; setup].', 'grouped');
hb(1).FaceColor = [0 0.4470 0.7410];     % blue for End-to-End
hb(2).FaceColor = [0.8500 0.3250 0.0980]; % orange for Set-Up
ylabel('Delay (s)')
ylim([0, max([e2e, setup]) * 1.2])

% X-axis setup
set(gca, 'XTick', x, 'XTickLabel', brokers)
xtickangle(45)

% Right Y-axis: line plot
yyaxis right
plot(x, sub, '-o', 'LineWidth', 2, 'Color', [0.5 0.5 0.5])
ylabel('Subscription Delay')
ylim([0, max(sub) * 1.2])

% Title and legend
title('''End to End'' vs ''Set-Up'' vs ''Subscription'' Delays')
legend({'End to End Delay', 'Set-Up Delay', 'Subscription Delay'}, 'Location', 'northwest')

grid on
box on
