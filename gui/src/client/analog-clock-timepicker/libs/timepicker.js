
/****************************************************
 * Directly Draggable Analog-Clock Style Timepicker *
 *                                                  *
 * Design by ZulNs @Yogyakarta, February 2016       *
 ****************************************************/

export function Timepicker(isClockMode, is24HoursSystem, selectedHours, selectedMinutes, selectedSeconds) {
	isClockMode = !!isClockMode;
	is24HoursSystem = !!is24HoursSystem;
	selectedHours = selectedHours === undefined ? new Date().getHours() : ~~selectedHours % 24;
	selectedMinutes = selectedMinutes === undefined ? new Date().getMinutes() : ~~selectedMinutes % 60;
	selectedSeconds = selectedSeconds === undefined ? new Date().getSeconds() : ~~selectedSeconds % 60;

	// var clockDate = new Date();
	// clockDate.setHours(0,0,0,0);
	
	var self = this,
		timepicker = document.createElement('div'),
		clockFace = document.createElement('canvas'),
		hourHand = document.createElement('canvas'),
		minuteHand = document.createElement('canvas'),
		secondHand = document.createElement('canvas'),
		pickedTime = document.createElement('div'),
		pickedDate = document.createElement('div'),
		hourSystemButton = document.createElement('div'),
		okButton = document.createElement('div'),
		displayStyle = 'block',
		isHidden = true,
		isPM = selectedHours >= 12,
		lastIsPM = isPM,
		isHourHand,
		isMinuteHand,
		clockDate,
		clockDateIntervalSize = 10,
		clockTimestamp,
		isReverseRotate,
		isDragging = false,
		isFiredByMouse = false,
		touchId,
		lastHourDeg,
		lastMinuteDeg,
		lastSecondDeg,
		centerX,
		centerY,
		cssTransform = Timepicker.getSupportedTransformProp(),
		secondTimer,


	handleMouseDown = function(e) {
		if (!isDragging) {
			window.clearInterval(secondTimer); // stop the clock moving forward
			e = e || window.event;
			e.preventDefault();
			e.stopPropagation();
			isFiredByMouse = true;
			isHourHand = e.target === hourHand;
			isMinuteHand = e.target === minuteHand;
			onPointerStart(e.pageX, e.pageY);
		}
	},
	
	handleMouseMove = function(e) {
		if (isDragging && isFiredByMouse) {
			e = e || window.event;
			e.preventDefault();
			onPointerMove(e.pageX, e.pageY);
		}
	},
	
	handleMouseUp = function(e) {
		if (isDragging && isFiredByMouse) {
			// startClockDateInterval();
			e = e || window.event;
			e.preventDefault();
			isDragging = false;
		}
	},
	
	handleTouchStart = function(e) {
		e = e || window.event;
		if (isDragging && !isFiredByMouse && e.touches.length == 1) isDragging = false;
		if (!isDragging) {
			var touch = e.changedTouches[0];
			e.preventDefault();
			//e.stopPropagation();
			isFiredByMouse = false;
			touchId = touch.identifier;
			isHourHand = touch.target === hourHand;
			isMinuteHand = touch.target === minuteHand;
			onPointerStart(touch.pageX, touch.pageY);
		}
	},
	
	handleTouchMove = function(e) {
		if (isDragging && !isFiredByMouse) {
			e = e || window.event;
			var touches = e.changedTouches, touch;
			for (var i = 0; i < touches.length; i++) {
				touch = touches[i];
				if (touch.identifier === touchId) {
					e.preventDefault();
					onPointerMove(touch.pageX, touch.pageY);
					break;
				}
			}
		}
	},
	
	handleTouchEnd = function(e) {
		if (isDragging && !isFiredByMouse) {
			e = e || window.event;
			var touches = e.changedTouches, touch;
			for (var i = 0; i < touches.length; i++) {
				touch = touches[i];
				if (touch.identifier === touchId) {
					e.preventDefault();
					isDragging = false;
					return;
				}
			}
		}
	},

	updateLastMinuteDeg = function(pseudo_deg, manual=false) {
		if ((270 < lastMinuteDeg && lastMinuteDeg < 360 && 0 <= pseudo_deg && pseudo_deg < 90) || (270 < pseudo_deg && pseudo_deg < 360 && 0 <= lastMinuteDeg && lastMinuteDeg < 90)) {
			lastHourDeg = lastHourDeg + (pseudo_deg - lastMinuteDeg - Math.sign(pseudo_deg - lastMinuteDeg) * 360) / 12;
			if (lastHourDeg < 0) lastHourDeg += 360;
			lastHourDeg %= 360;
			if (345 < lastHourDeg || lastHourDeg < 15) isPM = !isPM;
		}
		else {
			lastHourDeg = lastHourDeg + (pseudo_deg - lastMinuteDeg) / 12;
			if (lastHourDeg < 0) lastHourDeg += 360;
			lastHourDeg %= 360;
		}
		lastMinuteDeg = pseudo_deg;

		if (!manual) {
			rotateElement(minuteHand, lastMinuteDeg);
		}
		rotateElement(hourHand, lastHourDeg);
	},
	
	onPointerStart = function(currentX, currentY) {
		isDragging = true;
		centerX = timepicker.offsetLeft + hourHand.offsetLeft + 10;
		centerY = timepicker.offsetTop + hourHand.offsetTop + 70;
		var last = isHourHand ? lastHourDeg : isMinuteHand ? lastMinuteDeg : lastSecondDeg,
			deg = -Math.atan2(centerX - currentX, centerY - currentY) * 180 / Math.PI,
			dif = Math.abs(deg - last);
		isReverseRotate = (160 < dif && dif < 200);
	},
	
	onPointerMove = function(currentX, currentY) {
		var deg, last, target;
		if (currentX !== centerX || currentY !== centerY) {
			deg = -Math.atan2(centerX - currentX, centerY - currentY) * 180 / Math.PI;
			if (isReverseRotate) deg = deg - 180;
			if (deg < 0) deg += 360;
			target = isHourHand ? hourHand : isMinuteHand ? minuteHand : secondHand;
			rotateElement(target, deg);
			lastIsPM = isPM;
			var manual;
			if (isHourHand) {
				if ((0 <= deg && deg < 90 && 270 < lastHourDeg && lastHourDeg < 360) || (0 <= lastHourDeg && lastHourDeg < 90 && 270 < deg && deg < 360)) isPM = !isPM;
			
				lastHourDeg = deg;
				lastMinuteDeg = deg % 30 * 12;
				rotateElement(minuteHand, lastMinuteDeg);
				lastSecondDeg = lastMinuteDeg % 6 * 60;
				rotateElement(secondHand, lastSecondDeg);
			} else if (isMinuteHand) {
				updateLastMinuteDeg(deg, manual=true);
				lastSecondDeg = lastMinuteDeg % 6 * 60;
				rotateElement(secondHand, lastSecondDeg);
			} else {
				if ((270 < lastSecondDeg && lastSecondDeg < 360 && 0 <= deg && deg < 90) || (270 < deg && deg < 360 && 0 <= lastSecondDeg && lastSecondDeg < 90)) {

					var pseudo_deg = lastMinuteDeg + (deg - lastSecondDeg - Math.sign(deg - lastSecondDeg) * 360) / 60;
					if (pseudo_deg < 0) pseudo_deg += 360;
					pseudo_deg %= 360;
					updateLastMinuteDeg(pseudo_deg, manual=false);					
				} else {
					pseudo_deg = lastMinuteDeg + (deg - lastSecondDeg) / 60;
					if (pseudo_deg < 0) pseudo_deg += 360;
					pseudo_deg %= 360;
					updateLastMinuteDeg(pseudo_deg, manual=false);
				}
				lastSecondDeg = deg;				
			}
			
			selectedMinutes = 6 * lastHourDeg / 180;
			selectedHours = ~~selectedMinutes;
			selectedMinutes = Math.floor((selectedMinutes - selectedHours) * 60);
			selectedSeconds = parseFloat((lastSecondDeg / 6).toFixed(3));
			if (isPM) selectedHours += 12;

			if (lastIsPM && !isPM && selectedHours < 3) { // if we've gone from PM to AM and time's less then 3:00, we've gone forward a day...
				// console.log("Forwards a day");
				clockDate.setDate(clockDate.getDate() + 1)
				// clockDate.setHours(0,0,0,0);
					
			} else if (!lastIsPM && isPM && selectedHours > 21) { // else if we've gone from AM to PM and time's greater than 21:00, we've gone backwards a day
				// console.log("Backwards a day");
				clockDate.setDate(clockDate.getDate() - 1)
				// clockDate.setHours(0,0,0,0);
			}

			updateClockDate();
			updatePickedTime();
			
		}
	},
	
	handleChangeHourSystem = function() {
		is24HoursSystem = !is24HoursSystem;
		label24HoursSystem();
		updatePickedTime();
	},
	
	handleOkButton = function() {
		// self.hide();
		updateClockTime();
		if (typeof self.callback === 'function') self.callback();
	},
	
	updatePickedTime = function() {
		// console.log("You picked "+getPickedTimeString());
		pickedTime.innerHTML = getPickedTimeString();
		
		pickedDate.innerHTML = getPickedDateString();
		
		if (typeof self.callback === 'function') self.callback();
	},

	setClockDateToNow = function() {
		clockDate = new Date();
	},
		
	updateClockDate = function() {
		clockDate.setHours(selectedHours,selectedMinutes,selectedSeconds,0);
	},
	
	// startClockDateInterval = function() {
	// 	secondTimer = window.setInterval(moveClockDateForward, clockDateIntervalSize);
	// },
		
	updateClockTime = function() {
		selectedHours = new Date().getHours();
		selectedMinutes = new Date().getMinutes();
		selectedSeconds = new Date().getSeconds();
		
		setClockDateToNow();

		isPM = selectedHours >= 12;
		
		updateClockPointers();
		// if (selectedSeconds === 0) updatePickedTime();
		updatePickedTime();
		
	},
	
	updateClockPointers = function() {
		lastSecondDeg = selectedSeconds * 6;
		lastMinuteDeg = (selectedMinutes + lastSecondDeg / 360) * 6;
		lastHourDeg = (selectedHours % 12 + lastMinuteDeg / 360) * 30;
		rotateElement(hourHand, lastHourDeg);
		rotateElement(minuteHand, lastMinuteDeg);
		rotateElement(secondHand, lastSecondDeg);
	},

	getPickedDateString = function() {
		var pts = clockDate.toLocaleDateString();
		return pts;	
	},
	
	getPickedTimeString = function() {
		var pts = ('0' + (is24HoursSystem ? selectedHours : selectedHours % 12 === 0 ? 12 : selectedHours % 12)).slice(-2) + ':' + ('0' + selectedMinutes).slice(-2);
		if (!is24HoursSystem) pts += ' ' + (isPM ? 'PM' : 'AM');
		return pts;
	},
	
	label24HoursSystem = function() {
		hourSystemButton.innerHTML = (is24HoursSystem ? '12' : '24') + 'H';
	},
	
	rotateElement = function(elm, deg) {
		elm.style[cssTransform] = 'rotate(' + deg + 'deg)';
	},

	
	setTimepickerDisplay = function() {
		timepicker.style.display = isHidden ? 'none' : displayStyle;
	},
	
	scrollToFix = function() {
		var dw = document.body.offsetWidth,
			vw = window.innerWidth,
			vh = window.innerHeight,
			rect = timepicker.getBoundingClientRect(),
			hsSpc = dw > vw ? 20 : 0,
			scrollX = rect.left < 0 ? rect.left : 0,
			scrollY = rect.bottom - rect.top > vh ? rect.top : rect.bottom > vh - hsSpc ? rect.bottom - vh + hsSpc : 0;
		window.scrollBy(scrollX, scrollY);
	},
	
	addEvents = function() {
		Timepicker.addEvent(hourHand, 'mousedown', handleMouseDown);
		Timepicker.addEvent(minuteHand, 'mousedown', handleMouseDown);
		Timepicker.addEvent(secondHand, 'mousedown', handleMouseDown);
		Timepicker.addEvent(document, 'mousemove', handleMouseMove);
		Timepicker.addEvent(document, 'mouseup', handleMouseUp);
		if ('touchstart' in window || navigator.maxTouchPoints > 0 || navigator.msMaxTouchPoints > 0) {
			Timepicker.addEvent(hourHand, 'touchstart', handleTouchStart);
			Timepicker.addEvent(hourHand, 'touchmove', handleTouchMove);
			Timepicker.addEvent(hourHand, 'touchcancel', handleTouchEnd);
			Timepicker.addEvent(hourHand, 'touchend', handleTouchEnd);
			Timepicker.addEvent(minuteHand, 'touchstart', handleTouchStart);
			Timepicker.addEvent(minuteHand, 'touchmove', handleTouchMove);
			Timepicker.addEvent(minuteHand, 'touchcancel', handleTouchEnd);
			Timepicker.addEvent(minuteHand, 'touchend', handleTouchEnd);
			Timepicker.addEvent(secondHand, 'touchstart', handleTouchStart);
			Timepicker.addEvent(secondHand, 'touchmove', handleTouchMove);
			Timepicker.addEvent(secondHand, 'touchcancel', handleTouchEnd);
			Timepicker.addEvent(secondHand, 'touchend', handleTouchEnd);

		}
	},
	
	removeEvents = function() {
		Timepicker.removeEvent(hourHand, 'mousedown', handleMouseDown);
		Timepicker.removeEvent(minuteHand, 'mousedown', handleMouseDown);
		Timepicker.removeEvent(secondHand, 'mousedown', handleMouseDown);
		Timepicker.removeEvent(document, 'mousemove', handleMouseMove);
		Timepicker.removeEvent(document, 'mouseup', handleMouseUp);
		if ('touchstart' in window || navigator.maxTouchPoints > 0 || navigator.msMaxTouchPoints > 0) {
			Timepicker.removeEvent(hourHand, 'touchstart', handleTouchStart);
			Timepicker.removeEvent(hourHand, 'touchmove', handleTouchMove);
			Timepicker.removeEvent(hourHand, 'touchcancel', handleTouchEnd);
			Timepicker.removeEvent(hourHand, 'touchend', handleTouchEnd);
			Timepicker.removeEvent(minuteHand, 'touchstart', handleTouchStart);
			Timepicker.removeEvent(minuteHand, 'touchmove', handleTouchMove);
			Timepicker.removeEvent(minuteHand, 'touchcancel', handleTouchEnd);
			Timepicker.removeEvent(minuteHand, 'touchend', handleTouchEnd);
			Timepicker.removeEvent(secondHand, 'touchstart', handleTouchStart);
			Timepicker.removeEvent(secondHand, 'touchmove', handleTouchMove);
			Timepicker.removeEvent(secondHand, 'touchcancel', handleTouchEnd);
			Timepicker.removeEvent(secondHand, 'touchend', handleTouchEnd);

		}
	},
	
	createTimepicker = function() {
		if (!cssTransform) {
			self.destroy();
			alert('Sorry, your browser not support CSS transform!');
			return
		}
		// Initialize
		timepicker.classList.add('timepicker');
		clockFace.classList.add('clock-face');
		hourHand.classList.add('hour-hand');
		minuteHand.classList.add('minute-hand');
		secondHand.classList.add('second-hand');
		pickedTime.classList.add('picked-time');
		pickedDate.classList.add('picked-date');
		hourSystemButton.classList.add('button');
		hourSystemButton.classList.add('hour');
		hourSystemButton.style.padding = '0px';
		okButton.classList.add('button');
		okButton.classList.add('ok');
		okButton.style.padding = '0px';
		clockFace.setAttribute('width', 240);
		clockFace.setAttribute('height', 240);
		hourHand.setAttribute('width', 20);
		hourHand.setAttribute('height', 90);
		minuteHand.setAttribute('width', 12);
		minuteHand.setAttribute('height', 110);
		secondHand.setAttribute('width', 8);
		secondHand.setAttribute('height', 120);
		label24HoursSystem();
		okButton.innerHTML = 'Now';
		setTimepickerDisplay();
		timepicker.appendChild(clockFace);
		timepicker.appendChild(hourHand);
		timepicker.appendChild(minuteHand);
		timepicker.appendChild(secondHand);
		timepicker.appendChild(pickedTime);
		timepicker.appendChild(pickedDate);
		timepicker.appendChild(hourSystemButton);
		timepicker.appendChild(okButton);
		if (clockFace.getContext){
			// Create clock surface
			var ctx = clockFace.getContext('2d');
			ctx.strokeStyle = '#333';
			ctx.beginPath();
			ctx.arc(120, 120, 119, 0, 2 * Math.PI);
			ctx.stroke();
			var radGrd = ctx.createRadialGradient(100, 100, 140, 100, 100, 20);
			radGrd.addColorStop(0, '#fff');
			radGrd.addColorStop(1, '#ddd');
			ctx.fillStyle = radGrd;
			ctx.beginPath();
			ctx.arc(120, 120, 118, 0, 2 * Math.PI);
			ctx.fill();
			ctx.translate(120, 120);
			ctx.fillStyle = '#333';
			for (var i = 0; i < 12; i++) {
				ctx.beginPath();
				ctx.arc(0, -110, 3, 0, 2 * Math.PI);
				ctx.fill();
				ctx.rotate(Math.PI / 30);
				for (var j = 0; j < 4; j++) {
					ctx.beginPath();
					ctx.arc(0, -110, 2, 0, 2 * Math.PI);
					ctx.fill();
					ctx.rotate(Math.PI / 30);
				}
			}
			ctx.font = '16px serif';
			ctx.textAlign = 'center';
			ctx.textBaseline = 'middle';
			for (var i = 1; i <= 12; i++) {
				ctx.fillText(i, 94 * Math.sin(i * Math.PI / 6), -94 * Math.cos(i * Math.PI / 6));
			}
			// Create hour hand
			ctx = hourHand.getContext('2d');
			var radGrd = ctx.createRadialGradient(0, 0, 90, 70, 70, 20);
			radGrd.addColorStop(0, '#e40');
			radGrd.addColorStop(1, '#f51');
			ctx.fillStyle = radGrd;
			ctx.beginPath();
			ctx.moveTo(10, 0);
			ctx.lineTo(0, 90);
			ctx.lineTo(20, 90);
			ctx.lineTo(10, 0);
			ctx.fill();
			// Create minute hand
			ctx = minuteHand.getContext('2d');
			var radGrd = ctx.createRadialGradient(0, 0, 110, 90, 90, 20);
			radGrd.addColorStop(0, '#06e');
			radGrd.addColorStop(1, '#17f');
			ctx.fillStyle = radGrd;
			ctx.beginPath();
			ctx.moveTo(6, 0);
			ctx.lineTo(0, 110);
			ctx.lineTo(12, 110);
			ctx.lineTo(6, 0);
			ctx.fill();
			ctx.fillStyle = '#000';
			ctx.beginPath();
			ctx.arc(6, 90, 2, 0, 2 * Math.PI);
			ctx.fill();
			// Create second hand
			ctx = secondHand.getContext('2d');
			var radGrd = ctx.createRadialGradient(0, 0, 120, 100, 100, 20);
			radGrd.addColorStop(0, '#3a3');
			radGrd.addColorStop(1, '#4b4');
			ctx.fillStyle = radGrd;
			ctx.beginPath();
			ctx.moveTo(4, 0);
			ctx.lineTo(0, 120);
			ctx.lineTo(8, 120);
			ctx.lineTo(4, 0);
			ctx.fill();
			ctx.fillStyle = '#000';
			ctx.beginPath();
			ctx.arc(4, 90, 2, 0, 2 * Math.PI);
			ctx.fill();
			// Finalize
			Timepicker.addEvent(hourSystemButton, 'click', handleChangeHourSystem);
			Timepicker.addEvent(okButton, 'click', handleOkButton);
			
			if (isClockMode) secondTimer = window.setInterval(updateClockTime, 1000);
			else {
				addEvents();
				Timepicker.setCursor(hourHand, true);
				Timepicker.setCursor(minuteHand, true);
				Timepicker.setCursor(secondHand, true);
				// secondHand.style.display = 'none';
				// startClockDateInterval();
			}

			setClockDateToNow();
			updateClockDate();
			updateClockPointers();
			updatePickedTime();

			
		}
		else {
			self.destroy();
			alert('Sorry, your browser not support HTML canvas!');
		}
	};
	
	this.getElement = function() {
		return timepicker;
	};
	
	this.getHours = function() {
		return selectedHours;
	};
	
	this.getMinutes = function() {
		return selectedMinutes;
	};
	
	this.getTimeString = function() {
		return getPickedTimeString();
	};

	this.getDateString = function() {
		return getPickedDateString();
	};


	this.getTimestamp = function() {
		return +clockDate;
	};

	this.isClockMode = function() {
		return isClockMode;
	};
	
	this.is24HoursSystem = function() {
		return is24HoursSystem;
	};
	
	this.isHidden = function() {
		return isHidden;
	};

	
	this.moveClockDateForward = function(elapsedMilliseconds) {

		if (isDragging) return +clockDate; // Don't move clock hands forward if they're being dragged

		var selectedMilliseconds = clockDate.getMilliseconds();
		// add elapsedMilliseconds to clockDate
		clockDate.setMilliseconds(selectedMilliseconds + elapsedMilliseconds);

		selectedHours = clockDate.getHours();
		selectedMinutes = clockDate.getMinutes();
		selectedSeconds = clockDate.getSeconds();
		selectedMilliseconds = clockDate.getMilliseconds();
		
		isPM = selectedHours >= 12;
		if (selectedMilliseconds <= 100) updateClockPointers(); // Since the clock has 1 second precision, if the current millesconds are less than 100, we'll assume we've crossed a point where we should move the hands 
		

		if (selectedSeconds < 5) updatePickedTime(); // Since pickedTime only has minute precision, if the current seconds are less than 5, we'll assume we've crossed a point where we should update pickedTime

		return +clockDate;

	};

	
	this.setHours = function(hours) {
		if (!isNaN(hours)) selectedHours = parseInt(hours);
		if (isClockMode) updateClockPointers();
		updatePickedTime();
	};
	
	this.setMinutes = function(minutes) {
		if (!isNaN(minutes)) selectedMinutes = parseInt(minutes);
		if (isClockMode) updateClockPointers();
		updatePickedTime();
	};
	
	this.setSeconds = function(seconds) {
		if (!isNaN(seconds)) selectedSeconds = parseFloat(seconds).toFixed(3);
		if (isClockMode) updateClockPointers();
		updatePickedTime();
	};
	
	this.changeClockMode = function() {
		isClockMode = !isClockMode;
		Timepicker.setCursor(hourHand, !isClockMode);
		Timepicker.setCursor(minuteHand, !isClockMode);
		Timepicker.setCursor(secondHand, !isClockMode);
		// secondHand.style.display = isClockMode ? '' : 'none';
		if (isClockMode) {
			removeEvents();
			updateClockTime();
			updatePickedTime();
			secondTimer = window.setInterval(updateClockTime, 1000);
		}
		else {
			// startClockDateInterval();
			addEvents();
		}
	};
	
	this.changeHourSystem = function() {
		handleChangeHourSystem();
	};
	
	this.show = function() {
		if (isHidden) {
			isHidden = !isHidden;
			setTimepickerDisplay();
			scrollToFix();
		}
	};
	
	this.hide = function() {
		if (!isHidden) {
			isHidden = !isHidden;
			setTimepickerDisplay();
		}
	};
	
	this.destroy = function() {
		window.clearInterval(secondTimer);
		timepicker.remove();
		self = null;
	};
	
	this.setDisplayStyle = function(style) {
		displayStyle = style;
		setTimepickerDisplay();
	};
	
	this.callback;
	
	createTimepicker();
}

Timepicker.addEvent = function(elm, evt, callback) {
	if (window.addEventListener) elm.addEventListener(evt, callback);
	else elm.attachEvent('on' + evt, callback);
};

Timepicker.removeEvent = function(elm, evt, callback) {
	if (window.addEventListener) elm.removeEventListener(evt, callback);
	else elm.detachEvent('on' + evt, callback);
};

Timepicker.setCursor = function(elm, pointer) {
	elm.style.cursor = pointer ? 'pointer' : 'default';
};

Timepicker.getSupportedTransformProp = function() {
	var props = ['transform', 'MozTransform', 'WebkitTransfor', 'msTransform', 'OTransform'],
		root = document.documentElement;
	for (var i = 0; i < props.length; i++)
		if (props[i] in root.style) return props[i];
	return null;
};
