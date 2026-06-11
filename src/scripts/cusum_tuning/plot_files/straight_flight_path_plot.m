% Straight Flight Plan with Spoof Start Distance
clear; clc; close all;

% Flight plan points
x = [0 0 0 0 0 0];
y = [0 22.2 44.4 66.7 88.9 111.1];

% Create figure
figure('Color','w');
plot(x, y, '-o', 'LineWidth', 2, 'MarkerSize', 8);
hold on;

% Mark spoof start exactly at 25 m with an orange X
plot(0, 25, 'x', ...
    'Color', [1 0.5 0], ...      % orange
    'MarkerSize', 14, ...
    'LineWidth', 2.5);

% Label flight plan points
for i = 1:length(x)
    text(x(i)+1.5, y(i)+1.5, num2str(i), 'FontSize', 12);
end

% Label the spoof point
text(2.2, 21.5, '25 m', 'FontSize', 12, 'Color', 'k');

% Title and axis labels
title('Straight Flight Plan with Spoof Start Distance', 'FontSize', 18);
xlabel('East from start (m)', 'FontSize', 14);
ylabel('North from start (m)', 'FontSize', 14);

% Legend
legend('Flight plan', '25 m travelled', 'Location', 'northeast');

% Axis formatting
xlim([-62 62]);
ylim([-5 116]);
grid on;
set(gca, 'FontSize', 14);