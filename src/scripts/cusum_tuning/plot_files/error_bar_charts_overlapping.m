%% layered_mean_detection_time_by_path.m
% Creates one layered/overlaid bar chart comparing mean detection time
% for each detector on each flight path.
%
% Each x-axis position = one CSV/path.
% Each detector bar starts at zero.
% Bars are drawn on top of each other using transparency.
%
% Adaptive CUSUM^2 is not shown for the straight path.

clear; clc; close all;

%% CSV files and labels
csvDir = 'csv_run_files';

files = {
    fullfile(csvDir, 'straight_spoofed_25.csv')
    fullfile(csvDir, 'turns_spoofed_100.csv')
    fullfile(csvDir, 'turns_spoofed_140.csv')
    fullfile(csvDir, 'turns_spoofed_275.csv')
    fullfile(csvDir, 'blind_spoofed_65.csv')
    fullfile(csvDir, 'blind_spoofed_160.csv')
};

pathLabels = {
    'straight spoofed 25'
    'turns spoofed 100'
    'turns spoofed 140'
    'turns spoofed 275'
    'blind spoofed 65'
    'blind spoofed 160'
};

methods = {
    'SSDGOF',            'SSDGOF_time'
    'Standard CUSUM',    'CUSUM_time'
    'Adaptive CUSUM^2',  'adapt_CUSUM_time'
};

%% Compute mean detection times
nPaths = numel(files);
nMethods = size(methods, 1);

means = nan(nPaths, nMethods);
counts = zeros(nPaths, nMethods);

for i = 1:nPaths
    T = readtable(files{i});

    for j = 1:nMethods
        colName = methods{j, 2};
        vals = toNumericVector(T.(colName));

        % Ignore null / missing / NaN values
        vals = vals(~isnan(vals));

        counts(i, j) = numel(vals);

        if ~isempty(vals)
            means(i, j) = mean(vals);
        end
    end
end

%% Do not show Adaptive CUSUM^2 for straight path
% Row 1 = straight path
% Column 3 = Adaptive CUSUM^2
means(1, 3) = NaN;
counts(1, 3) = 0;

%% Prepare plot values
yPlot = means;
noDetections = isnan(yPlot);
yPlot(noDetections) = 0;

%% Plot layered bars
figure('Name', 'Layered mean detection time by path and detector');

x = 1:nPaths;
hold on;

% Draw largest/oldest baseline first, then faster methods on top.
% You can change this order if wanted.
plotOrder = [1 2 3];

barWidths = [0.75, 0.50, 0.30];

for idx = 1:numel(plotOrder)
    j = plotOrder(idx);

    y = yPlot(:, j);

    % Remove Adaptive CUSUM^2 straight path by setting that bar invisible/zero
    if j == 3
        y(1) = NaN;
    end

    b = bar(x, y, barWidths(idx), ...
        'DisplayName', methods{j, 1});

    b.FaceAlpha = 0.65;
    b.EdgeAlpha = 0.8;
end

ylabel('Mean detection time after spoof start (s)');
title('Mean detection time by path and detector');
grid on;

set(gca, 'XTick', x);
set(gca, 'XTickLabel', pathLabels);
xtickangle(35);

legend('Location', 'best');

%% Set y-axis limit
yMax = max(yPlot, [], 'all');

if isempty(yMax) || isnan(yMax) || yMax == 0
    yMax = 1;
end

ylim([0, yMax * 1.2]);

%% Annotate no-detection cases
for i = 1:nPaths
    for j = 1:nMethods

        % Skip Adaptive CUSUM^2 on straight path completely
        if i == 1 && j == 3
            continue;
        end

     
    end
end

%% Save figure
saveas(gcf, 'layered_mean_detection_time_by_path.png');

%% Save mean values to CSV
resultsTable = table( ...
    pathLabels(:), ...
    means(:, 1), ...
    means(:, 2), ...
    means(:, 3), ...
    counts(:, 1), ...
    counts(:, 2), ...
    counts(:, 3), ...
    'VariableNames', { ...
        'Path', ...
        'Mean_SSDGOF_time_s', ...
        'Mean_Standard_CUSUM_time_s', ...
        'Mean_Adaptive_CUSUM2_time_s', ...
        'SSDGOF_n', ...
        'Standard_CUSUM_n', ...
        'Adaptive_CUSUM2_n' ...
    } ...
);

writetable(resultsTable, 'layered_mean_detection_time_by_path_values.csv');

disp(resultsTable);

%% Helper function
function vals = toNumericVector(x)
    if isnumeric(x)
        vals = x;
    elseif iscell(x)
        vals = str2double(x);
    elseif iscategorical(x)
        vals = str2double(cellstr(x));
    else
        vals = str2double(cellstr(string(x)));
    end

    vals = vals(:);
end