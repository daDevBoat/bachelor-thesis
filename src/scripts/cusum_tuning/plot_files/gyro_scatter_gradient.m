% Scatter plot from files 1.csv to 25.csv in turns_control
% X axis: running sum of column 2
% Y axis: absolute difference between column 1 and column 2
% IQR method: points above upper bound are orange
% Other points are blue-gradient colored by local point density

folderPath = "../flight_logs/turns_control";

allX = [];
allY = [];

for fileNum = 1:25
    filename = fullfile(folderPath, sprintf("%d.csv", fileNum));

    if ~isfile(filename)
        warning("Skipping %s: file does not exist.", filename);
        continue;
    end

    data = readmatrix(filename);

    if size(data, 2) < 2
        warning("Skipping %s: file has fewer than 2 columns.", filename);
        continue;
    end

    % Read first two columns
    col1 = data(:, 1);
    col2 = data(:, 2);

    % Remove rows with NaN values, useful if the CSV has a header row
    validRows = ~isnan(col1) & ~isnan(col2);
    col1 = col1(validRows);
    col2 = col2(validRows);

    % X axis: running sum of column 2
    x = cumsum(col2);

    % Y axis: absolute difference between column 1 and column 2
    y = abs(col1 - col2);

    allX = [allX; x];
    allY = [allY; y];
end

if isempty(allX)
    error("No valid data was found in the CSV files.");
end

% IQR method on all Y values
iqrMultiplier = 1.5;

Q1 = quantile(allY, 0.25);
Q3 = quantile(allY, 0.75);
IQR_value = Q3 - Q1;
upperBound = Q3 + iqrMultiplier * IQR_value;

isAboveUpper = allY > upperBound;

% Separate normal and outlier points
xNormal = allX(~isAboveUpper);
yNormal = allY(~isAboveUpper);

xOutlier = allX(isAboveUpper);
yOutlier = allY(isAboveUpper);

% Estimate local density using 2D bins
numBins = 75;   % Increase for finer density, decrease for smoother density

[counts, xEdges, yEdges] = histcounts2(xNormal, yNormal, numBins);

xBin = discretize(xNormal, xEdges);
yBin = discretize(yNormal, yEdges);

density = zeros(size(xNormal));

validBins = ~isnan(xBin) & ~isnan(yBin);
density(validBins) = counts(sub2ind(size(counts), xBin(validBins), yBin(validBins)));

% Sort by density so denser points are drawn on top
[~, sortIdx] = sort(density);
xNormal = xNormal(sortIdx);
yNormal = yNormal(sortIdx);
density = density(sortIdx);

% Create scatter plot
figure;
hold on;

% Blue gradient for non-outlier points
scatter(xNormal, yNormal, 15, density, "filled");

% Make density colors saturate earlier
% Lower percentile = darker colors appear sooner
densityColorLimit = prctile(density(density > 0), 70);
clim([0 densityColorLimit]);

% Custom blue colormap: light blue to dark blue
blueMap = [
    linspace(0.75, 0.00, 256)', ...
    linspace(0.90, 0.20, 256)', ...
    linspace(1.00, 0.80, 256)'
];
colormap(blueMap);

cb = colorbar;
ylabel(cb, "Local point density");

% Orange outliers above upper IQR bound
scatter(xOutlier, yOutlier, 25, ...
    [0.8500 0.3250 0.0980], "filled");

% Upper bound line
yline(upperBound, "--", "Upper IQR bound", "LineWidth", 2);

xlabel("Running sum of column 2");
ylabel("|Column 1 - Column 2|");
title("Running sum vs absolute difference with IQR outliers");

legend("Not over upper bound, colored by density", ...
       "Over upper bound", ...
       "Upper bound", ...
       "Location", "best");

grid on;
hold off;

% Print values in command window
fprintf("Q1 = %.6f\n", Q1);
fprintf("Q3 = %.6f\n", Q3);
fprintf("IQR = %.6f\n", IQR_value);
fprintf("Upper bound = %.6f\n", upperBound);
fprintf("Number over upper bound = %d\n", sum(isAboveUpper));