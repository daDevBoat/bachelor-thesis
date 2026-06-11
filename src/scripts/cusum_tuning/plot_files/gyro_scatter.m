% Scatter plot from files 1.csv to 25.csv in turns_control
% X axis: running sum of column 2
% Y axis: absolute difference between column 1 and column 2
% IQR method: points above upper bound are orange, all others are blue

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

    % Check that the file has at least 2 columns
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

    % Store all points from all files
    allX = [allX; x];
    allY = [allY; y];
end

% IQR method on all Y values
Q1 = quantile(allY, 0.25);
Q3 = quantile(allY, 0.75);
IQR_value = Q3 - Q1;
upperBound = Q3 + 1.5 * IQR_value;

% Points above upper bound
isAboveUpper = allY > upperBound;

% Create scatter plot
figure;
hold on;

% Blue: normal points
scatter(allX(~isAboveUpper), allY(~isAboveUpper), 15, ...
    [0 0.4470 0.7410], "filled");

% Orange: points above upper bound
scatter(allX(isAboveUpper), allY(isAboveUpper), 20, ...
    [0.8500 0.3250 0.0980], "filled");

% Optional: draw the upper bound as a horizontal line
yline(upperBound, "--m", "LineWidth", 2);

xlabel("Distance travelled [m]");
ylabel("Absolute differance between optical flow and GPS per timestep [m]");
title("Difference between optical flow and GPS estimate on multiple turns control flights");

legend("Not over upper bound", "Over upper bound", "IQR Upper bound", ...
    "Location", "best");

grid on;
hold off;

% Print values in command window
fprintf("Q1 = %.6f\n", Q1);
fprintf("Q3 = %.6f\n", Q3);
fprintf("IQR = %.6f\n", IQR_value);
fprintf("Upper bound = %.6f\n", upperBound);
fprintf("Number over upper bound = %d\n", sum(isAboveUpper));