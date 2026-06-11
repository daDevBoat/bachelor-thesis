% plot_gyro_s_s_pos_s_neg_s_max.m
% Column 1 = x/distnc
% Column 2 = gyro_s
% Column 3 = s_pos
% Column 4 = s_neg

clear; clc; close all;

filename = 'uncapped_gyro.csv';

data = readmatrix(filename, 'NumHeaderLines', 1);
data(all(isnan(data), 2), :) = [];

x      = data(:, 1);
gyro_s = data(:, 2);
s_pos  = data(:, 3);
s_neg  = data(:, 4);

% Row-wise maximum of s_pos and s_neg for each x value
s_max = max(s_pos, s_neg);

threshold = 20.15;

%% First intersection between s_max and gyro_s
diff_gyro = s_max - gyro_s;

idx_gyro = find(diff_gyro(1:end-1) .* diff_gyro(2:end) <= 0, 1, 'first');

x_int_gyro = NaN;
y_int_gyro = NaN;

if ~isempty(idx_gyro)
    i = idx_gyro;

    x1 = x(i);
    x2 = x(i+1);

    d1 = diff_gyro(i);
    d2 = diff_gyro(i+1);

    if d1 == 0
        x_int_gyro = x1;
        y_int_gyro = s_max(i);
    elseif d2 == 0
        x_int_gyro = x2;
        y_int_gyro = s_max(i+1);
    else
        % Linear interpolation
        x_int_gyro = x1 - d1 * (x2 - x1) / (d2 - d1);
        y_int_gyro = interp1(x(i:i+1), s_max(i:i+1), x_int_gyro);
    end
end

%% First intersection between s_max and threshold line
diff_thresh = s_max - threshold;

idx_thresh = find(diff_thresh(1:end-1) .* diff_thresh(2:end) <= 0, 1, 'first');

x_int_thresh = NaN;
y_int_thresh = NaN;

if ~isempty(idx_thresh)
    i = idx_thresh;

    x1 = x(i);
    x2 = x(i+1);

    d1 = diff_thresh(i);
    d2 = diff_thresh(i+1);

    if d1 == 0
        x_int_thresh = x1;
        y_int_thresh = threshold;
    elseif d2 == 0
        x_int_thresh = x2;
        y_int_thresh = threshold;
    else
        % Linear interpolation
        x_int_thresh = x1 - d1 * (x2 - x1) / (d2 - d1);
        y_int_thresh = threshold;
    end
end

%% Plot
figure;

plot(x, gyro_s, 'LineWidth', 1.2);
hold on;
plot(x, s_pos,  'LineWidth', 1.2);
plot(x, s_neg,  'LineWidth', 1.2);
plot(x, s_max, '--' ,'LineWidth', 1.5);

% Dashed green threshold line at y = 20.15
yline(threshold, 'g--', 'LineWidth', 1.5);

hold off;

grid on;
xlabel('Distance [m]');
ylabel('CUSUM value');
title('Adaptive CUSUM analysis of control turns flight');

legend('S_G', ...
       'S^+', ...
       'S^-', ...
       'max(S^+, S^-)', ...
       'standard CUSUM threshold', ...
       'Location', 'best');