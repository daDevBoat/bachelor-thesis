%% error_bar_charts.m
% Creates one error-bar chart per detection method.
% Each bar = one CSV/path, using all runs in that CSV.
% Bar height = mean detection time after spoof start.
% Error bar = standard deviation across runs, ignoring null/NaN values.

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
    'SSDGOF',         'SSDGOF_time'
    'Standard CUSUM', 'CUSUM_time'
    'Adaptive CUSUM', 'adapt_CUSUM_time'
};

%% Choose error type: 'std' or 'sem'
errorType = 'std';

%% Compute means and errors
nPaths = numel(files);
nMethods = size(methods, 1);

means = nan(nPaths, nMethods);
errors = nan(nPaths, nMethods);
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

            switch lower(errorType)
                case 'std'
                    errors(i, j) = std(vals);
                case 'sem'
                    errors(i, j) = std(vals) / sqrt(numel(vals));
                otherwise
                    error('errorType must be ''std'' or ''sem''.');
            end
        end
    end
end

%% Plot one chart per method
for j = 1:nMethods
    methodName = methods{j, 1};

    y = means(:, j);
    e = errors(:, j);

    % For paths with no detections, plot zero-height bar and annotate it
    noDetections = isnan(y);

    yPlot = y;
    ePlot = e;

    yPlot(noDetections) = 0;
    ePlot(noDetections) = 0;

    figure('Name', methodName);

    x = 1:nPaths;

    bar(x, yPlot);
    hold on;

    errorbar(x, yPlot, ePlot, ...
        'k.', ...
        'LineWidth', 1.4, ...
        'CapSize', 12);

    ylabel('Detection time after spoof start (s)');
    title([methodName ' detection time by path']);
    grid on;

    set(gca, 'XTick', x);
    set(gca, 'XTickLabel', pathLabels);
    xtickangle(35);

    yMax = max(yPlot + ePlot);

    if isempty(yMax) || isnan(yMax) || yMax == 0
        yMax = 1;
    end

    ylim([0, yMax * 1.25]);

    % Annotate sample counts and no-detection cases
    for i = 1:nPaths
        if noDetections(i)
            text(i, 0.15 * yMax, 'no detections', ...
                'HorizontalAlignment', 'center', ...
                'Rotation', 90);
        else
            text(i, yPlot(i) + ePlot(i) + 0.03 * yMax, ...
                ['n=' num2str(counts(i, j))], ...
                'HorizontalAlignment', 'center');
        end
    end

    % Save figure as PNG
    safeName = regexprep(methodName, '\s+', '_');
    saveas(gcf, [safeName '_errorbar_chart.png']);
end

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