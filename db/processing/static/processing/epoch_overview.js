var selectedCell = {
  element: null,
  obsId: null,
  calObsId: null
};

var qaContextMenu = document.getElementById("qa-context-menu");

// Deselect the selected cell, if there is any cell selected
function deselectCell() {
  if (selectedCell.element !== null) {
    selectedCell.element.classList.remove("selected-cell");
    selectedCell.element = null;
    selectedCell.obsId = null;
    selectedCell.calObsId = null;
    qaContextMenu.style.display = "none";
  }
}

// Select the given cell
// But if it's already selected, deselect it
function selectCell(element, obsId, calObsId) {
  if (element == selectedCell.element) {
    deselectCell();

    qaContextMenu.style.display = "none";
  } else {
  deselectCell();
  element.classList.add("selected-cell");
  selectedCell.element = element;
  selectedCell.obsId = obsId;
  selectedCell.calObsId = calObsId;

  // Context menu for image cells
  qaContextMenu.style.display = "inline-flex";
  qaContextMenu.style.left = (element.offsetLeft + element.offsetWidth) + "px";
  qaContextMenu.style.top = element.offsetTop + "px";
  }
}

function setQa(quality) {

  // quality can only be {"good", "bad", "none"}
  if (quality !== "good" && quality !== "bad" && quality !== "none") {
    return;
  }

  const xhr = new XMLHttpRequest();
  xhr.open('PUT', "{% url 'set_qa' %}");
  xhr.setRequestHeader("X-CSRFToken", "{{ csrf_token }}");
  xhr.setRequestHeader("Content-type", "application/json");

  const data = {
    obs: selectedCell.obsId,
    calObs: selectedCell.calObsId,
    quality: quality
  };

  xhr.onload = () => {
    if (xhr.status != 200) {
      return;
    }

    // Do other stuff here (= change symbol)
    qaDiv = selectedCell.element.querySelector('.qa');

    if (quality === "good") {
      qaDiv.innerHTML = "&#x2713;";
      qaDiv.classList.add("cal-usable");
      qaDiv.classList.remove("cal-unusable");
      qaDiv.classList.remove("cal-unsure");
    } else if (quality === "bad") {
    qaDiv.innerHTML = "&#x274C;";
    qaDiv.classList.remove("cal-usable");
    qaDiv.classList.add("cal-unusable");
    qaDiv.classList.remove("cal-unsure");
    } else if (quality === "none") {
    qaDiv.innerHTML = "?";
    qaDiv.classList.remove("cal-usable");
    qaDiv.classList.remove("cal-unusable");
    qaDiv.classList.add("cal-unsure");
    }

    // Hide the context menu
    deselectCell();
  }

  console.log(data);
  xhr.send(JSON.stringify(data));

  // Set the symbol to be an hourglass
  qaDiv = selectedCell.element.querySelector('.qa');
  qaDiv.innerHTML = "&#8987;";
}

