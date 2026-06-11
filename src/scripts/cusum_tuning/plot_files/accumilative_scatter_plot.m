% Scatter plot from files 1.csv to 25.csv in turns_control
% Skip the first line of every CSV file
%
% X axis: cumulative sum of abs(column 3 - column 4)
% Y axis: cumulative sum of abs(column 1 - column 2)

folderPath = "../flight_logs/turns_control";

allX = [];
allY = [];

for fileNum = 1:25
    filename = fullfile(folderPath, sprintf("%d.csv", fileNum));

    if ~isfile(filename)
        warning("Skipping %s: file does not exist.", filename);
        continue;
    end

    % Read CSV data
    data = readmatrix(filename);

    % Skip first row
    data = data(2:end, :);

    % Check that the file has at least 4 columns
    if size(data, 2) < 4
        warning("Skipping %s: file has fewer than 4 columns.", filename);
        continue;
    end

    % Read needed columns
    col1 = data(:, 1);
    col2 = data(:, 2);
    col3 = data(:, 3);
    col4 = data(:, 4);

    % Remove rows with NaN values
    validRows = ~isnan(col1) & ~isnan(col2) & ~isnan(col3) & ~isnan(col4);

    col1 = col1(validRows);
    col2 = col2(validRows);
    col3 = col3(validRows);
    col4 = col4(validRows);

    % Base differences
    xDiff = abs(col3 - col4);
    yDiff = col1 - col2;

    % Accumulative / cumulative values within each CSV file
    x = cumsum(xDiff);
    y = cumsum(yDiff);

    % Store all points from all files
    allX = [allX; x];
    allY = [allY; y];
end

if isempty(allX)
    error("No valid data was found in the CSV files.");
end

% Create scatter plot
figure;
scatter(allX, allY, 15, "filled");

xlabel("Accumilative delta gyro magnitude");
ylabel("Accumilative diff Gps and OF");
title("Accumilative differences");

grid on;