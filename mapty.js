'use strict';

const API_URL = 'http://localhost:5000/api';
let authToken = null;

class Workout {
    date = new Date();
    id = (Date.now() + '').slice(-10);
    clicks = 0;

    constructor(coords, distance, duration) {
        this.coords = coords;
        this.distance = distance;
        this.duration = duration;
    }

    _setDescription() {
        const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
        this.description = `${this.type[0].toUpperCase()}${this.type.slice(1)} on ${
            months[this.date.getMonth()]
        } ${this.date.getDate()}`;
    }

    click() {
        this.clicks++;
    }
}

class Running extends Workout {
    type = 'running';

    constructor(coords, distance, duration, cadence) {
        super(coords, distance, duration);
        this.cadence = cadence;
        this.calcPace();
        this._setDescription();
    }

    calcPace() {
        this.pace = this.duration / this.distance;
        return this.pace;
    }
}

class Cycling extends Workout {
    type = 'cycling';

    constructor(coords, distance, duration, elevationGain) {
        super(coords, distance, duration);
        this.elevationGain = elevationGain;
        this.calcSpeed();
        this._setDescription();
    }

    calcSpeed() {
        this.speed = this.distance / (this.duration / 60);
        return this.speed;
    }
}

// DOM Elements
const form = document.querySelector('.form');
const containerWorkouts = document.querySelector('.workouts');
const inputType = document.querySelector('.form__input--type');
const inputDistance = document.querySelector('.form__input--distance');
const inputDuration = document.querySelector('.form__input--duration');
const inputCadence = document.querySelector('.form__input--cadence');
const inputElevation = document.querySelector('.form__input--elevation');

class App {
    #map;
    #mapZoomLevel = 13;
    #mapEvent;
    #workouts = [];

    constructor() {
        this._checkAuth();
        this._getPosition();
        this._getLocalStorage();

        form.addEventListener('submit', this._newWorkout.bind(this));
        inputType.addEventListener('change', this._toggleElevationField);
        containerWorkouts.addEventListener('click', this._moveToPopup.bind(this));
    }

    _checkAuth() {
        authToken = localStorage.getItem('authToken');
        if (!authToken) {
            this._showAuthModal();
        }
    }

    _showAuthModal() {
        const modal = document.createElement('div');
        modal.innerHTML = `
            <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); display: flex; justify-content: center; align-items: center; z-index: 9999;">
                <div style="background: white; padding: 30px; border-radius: 10px; min-width: 300px;">
                    <h2>Mapty Login</h2>
                    <input type="email" id="authEmail" placeholder="Email" style="width: 100%; padding: 10px; margin: 10px 0; box-sizing: border-box;">
                    <input type="password" id="authPassword" placeholder="Password" style="width: 100%; padding: 10px; margin: 10px 0; box-sizing: border-box;">
                    <button id="authLogin" style="width: 100%; padding: 10px; margin: 5px 0; background: #00c46a; color: white; border: none; border-radius: 5px; cursor: pointer;">Login</button>
                    <button id="authRegister" style="width: 100%; padding: 10px; margin: 5px 0; background: #0a8cff; color: white; border: none; border-radius: 5px; cursor: pointer;">Register</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        document.getElementById('authLogin').addEventListener('click', () => {
            this._login(document.getElementById('authEmail').value, document.getElementById('authPassword').value);
            modal.remove();
        });

        document.getElementById('authRegister').addEventListener('click', () => {
            this._register(document.getElementById('authEmail').value, document.getElementById('authPassword').value);
            modal.remove();
        });
    }

    async _login(email, password) {
        try {
            const response = await fetch(`${API_URL}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            const data = await response.json();
            if (response.ok) {
                authToken = data.token;
                localStorage.setItem('authToken', authToken);
                location.reload();
            } else {
                alert(data.message);
            }
        } catch (err) {
            console.error('Login error:', err);
            alert('Login failed');
        }
    }

    async _register(email, password) {
        try {
            const response = await fetch(`${API_URL}/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            const data = await response.json();
            if (response.ok) {
                authToken = data.token;
                localStorage.setItem('authToken', authToken);
                location.reload();
            } else {
                alert(data.message);
            }
        } catch (err) {
            console.error('Register error:', err);
            alert('Registration failed');
        }
    }

    _getPosition() {
        if (navigator.geolocation)
            navigator.geolocation.getCurrentPosition(
                this._loadMap.bind(this),
                function () {
                    alert('Could not get your position');
                }
            );
    }

    _loadMap(position) {
        const { latitude } = position.coords;
        const { longitude } = position.coords;
        const coords = [latitude, longitude];

        this.#map = L.map('map').setView(coords, this.#mapZoomLevel);

        L.tileLayer('https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        }).addTo(this.#map);

        this.#map.on('click', this._showForm.bind(this));

        this.#workouts.forEach(work => {
            this._renderWorkoutMarker(work);
        });
    }

    _showForm(mapE) {
        this.#mapEvent = mapE;
        form.classList.remove('hidden');
        inputDistance.focus();
    }

    _hideForm() {
        inputDistance.value = inputDuration.value = inputCadence.value = inputElevation.value = '';
        form.style.display = 'none';
        form.classList.add('hidden');
        setTimeout(() => (form.style.display = 'grid'), 1000);
    }

    _toggleElevationField() {
        inputElevation.closest('.form__row').classList.toggle('form__row--hidden');
        inputCadence.closest('.form__row').classList.toggle('form__row--hidden');
    }

    async _newWorkout(e) {
        const validInputs = (...inputs) => inputs.every(inp => Number.isFinite(inp));
        const allPositive = (...inputs) => inputs.every(inp => inp > 0);

        e.preventDefault();

        const type = inputType.value;
        const distance = +inputDistance.value;
        const duration = +inputDuration.value;
        const { lat, lng } = this.#mapEvent.latlng;
        let workout;

        if (type === 'running') {
            const cadence = +inputCadence.value;
            if (!validInputs(distance, duration, cadence) || !allPositive(distance, duration, cadence))
                return alert('Inputs have to be positive numbers!');
            workout = new Running([lat, lng], distance, duration, cadence);
        }

        if (type === 'cycling') {
            const elevation = +inputElevation.value;
            if (!validInputs(distance, duration, elevation) || !allPositive(distance, duration))
                return alert('Inputs have to be positive numbers!');
            workout = new Cycling([lat, lng], distance, duration, elevation);
        }

        this.#workouts.push(workout);
        this._renderWorkoutMarker(workout);
        this._renderWorkout(workout);
        this._hideForm();

        // Save to backend
        await this._saveWorkoutToServer(workout);
    }

    async _saveWorkoutToServer(workout) {
        try {
            const response = await fetch(`${API_URL}/workouts`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify({
                    type: workout.type,
                    distance: workout.distance,
                    duration: workout.duration,
                    coords: workout.coords,
                    date: workout.date.toISOString(),
                    description: workout.description,
                    cadence: workout.cadence,
                    pace: workout.pace,
                    elevationGain: workout.elevationGain,
                    speed: workout.speed
                })
            });
            if (!response.ok) alert('Failed to save workout');
        } catch (err) {
            console.error('Save error:', err);
            alert('Failed to save workout');
        }
    }

    _renderWorkoutMarker(workout) {
        L.marker(workout.coords)
            .addTo(this.#map)
            .bindPopup(
                L.popup({
                    maxWidth: 250,
                    minWidth: 100,
                    autoClose: false,
                    closeOnClick: false,
                    className: `${workout.type}-popup`,
                })
            )
            .setPopupContent(`${workout.type === 'running' ? '🏃‍♂️' : '🚴‍♀️'} ${workout.description}`)
            .openPopup();
    }

    _renderWorkout(workout) {
        let html = `
      <li class="workout workout--${workout.type}" data-id="${workout.id}">
        <h2 class="workout__title">${workout.description}</h2>
        <div class="workout__details">
          <span class="workout__icon">${workout.type === 'running' ? '🏃‍♂️' : '🚴‍♀️'}</span>
          <span class="workout__value">${workout.distance}</span>
          <span class="workout__unit">km</span>
        </div>
        <div class="workout__details">
          <span class="workout__icon">⏱</span>
          <span class="workout__value">${workout.duration}</span>
          <span class="workout__unit">min</span>
        </div>
    `;

        if (workout.type === 'running')
            html += `
        <div class="workout__details">
          <span class="workout__icon">⚡️</span>
          <span class="workout__value">${workout.pace.toFixed(1)}</span>
          <span class="workout__unit">min/km</span>
        </div>
        <div class="workout__details">
          <span class="workout__icon">🦶🏼</span>
          <span class="workout__value">${workout.cadence}</span>
          <span class="workout__unit">spm</span>
        </div>
      </li>
      `;

        if (workout.type === 'cycling')
            html += `
        <div class="workout__details">
          <span class="workout__icon">⚡️</span>
          <span class="workout__value">${workout.speed.toFixed(1)}</span>
          <span class="workout__unit">km/h</span>
        </div>
        <div class="workout__details">
          <span class="workout__icon">⛰</span>
          <span class="workout__value">${workout.elevationGain}</span>
          <span class="workout__unit">m</span>
        </div>
      </li>
      `;

        form.insertAdjacentHTML('afterend', html);
    }

    _moveToPopup(e) {
        if (!this.#map) return;
        const workoutEl = e.target.closest('.workout');
        if (!workoutEl) return;
        const workout = this.#workouts.find(work => work.id === workoutEl.dataset.id);
        this.#map.setView(workout.coords, this.#mapZoomLevel, {
            animate: true,
            pan: { duration: 1 },
        });
    }

    _setLocalStorage() {
        localStorage.setItem('workouts', JSON.stringify(this.#workouts));
    }

    async _getLocalStorage() {
        try {
            const response = await fetch(`${API_URL}/workouts`, {
                headers: { 'Authorization': `Bearer ${authToken}` }
            });
            const workouts = await response.json();
            
            workouts.forEach(data => {
                let workout;
                if (data.type === 'running') {
                    workout = new Running(data.coords, data.distance, data.duration, data.cadence);
                    workout.pace = data.pace;
                } else {
                    workout = new Cycling(data.coords, data.distance, data.duration, data.elevationGain);
                    workout.speed = data.speed;
                }
                workout.id = data.id;
                workout.date = new Date(data.date);
                workout.description = data.description;
                workout.clicks = data.clicks;
                this.#workouts.push(workout);
                this._renderWorkout(workout);
            });
        } catch (err) {
            console.error('Fetch error:', err);
        }
    }

    reset() {
        localStorage.removeItem('workouts');
        localStorage.removeItem('authToken');
        location.reload();
    }
}

const app = new App();