// auth.js
import { 
  getAuth, 
  createUserWithEmailAndPassword, 
  signInWithEmailAndPassword, 
  signOut, 
  onAuthStateChanged,
  updateProfile
} from "firebase/auth";
import { 
  getFirestore, 
  doc, 
  setDoc, 
  getDoc, 
  collection 
} from "firebase/firestore";
import { app } from './firebase';

// Initialize Firebase Auth and Firestore
const auth = getAuth(app);
const db = getFirestore(app);

// Sign up function
export const signUpUser = async (email, password, firstName, lastName) => {
  try {
    // Create user with email and password
    const userCredential = await createUserWithEmailAndPassword(auth, email, password);
    const user = userCredential.user;

    // Update the user's display name
    await updateProfile(user, {
      displayName: `${firstName} ${lastName}`
    });

    // Create user document in Firestore
    await setDoc(doc(db, 'users', user.uid), {
      uid: user.uid,
      email: email.toLowerCase(),
      firstName: firstName,
      lastName: lastName,
      displayName: `${firstName} ${lastName}`,
      createdAt: new Date().toISOString(),
      lastLoginAt: new Date().toISOString(),
      // Add any additional user fields you want
      preferences: {
        notifications: true,
        theme: 'light'
      },
      stats: {
        videosGenerated: 0,
        problemsSolved: 0
      }
    });

    return {
      success: true,
      user: user,
      message: 'Account created successfully!'
    };
  } catch (error) {
    console.error('Sign up error:', error);
    return {
      success: false,
      error: error.code,
      message: getErrorMessage(error.code)
    };
  }
};

// Sign in function
export const signInUser = async (email, password) => {
  try {
    const userCredential = await signInWithEmailAndPassword(auth, email, password);
    const user = userCredential.user;

    // Update last login time in Firestore
    const userDocRef = doc(db, 'users', user.uid);
    await setDoc(userDocRef, {
      lastLoginAt: new Date().toISOString()
    }, { merge: true });

    return {
      success: true,
      user: user,
      message: 'Signed in successfully!'
    };
  } catch (error) {
    console.error('Sign in error:', error);
    return {
      success: false,
      error: error.code,
      message: getErrorMessage(error.code)
    };
  }
};

// Sign out function
export const signOutUser = async () => {
  try {
    await signOut(auth);
    return {
      success: true,
      message: 'Signed out successfully!'
    };
  } catch (error) {
    console.error('Sign out error:', error);
    return {
      success: false,
      error: error.code,
      message: 'Error signing out. Please try again.'
    };
  }
};

// Get user data from Firestore
export const getUserData = async (uid) => {
  try {
    const userDoc = await getDoc(doc(db, 'users', uid));
    if (userDoc.exists()) {
      return {
        success: true,
        userData: userDoc.data()
      };
    } else {
      return {
        success: false,
        message: 'User data not found'
      };
    }
  } catch (error) {
    console.error('Error getting user data:', error);
    return {
      success: false,
      error: error.code,
      message: 'Error retrieving user data'
    };
  }
};

// Auth state observer
export const observeAuthState = (callback) => {
  return onAuthStateChanged(auth, callback);
};

// Helper function to get user-friendly error messages
const getErrorMessage = (errorCode) => {
  switch (errorCode) {
    case 'auth/email-already-in-use':
      return 'An account with this email already exists.';
    case 'auth/weak-password':
      return 'Password should be at least 6 characters long.';
    case 'auth/invalid-email':
      return 'Please enter a valid email address.';
    case 'auth/user-not-found':
      return 'No account found with this email address.';
    case 'auth/wrong-password':
      return 'Incorrect password. Please try again.';
    case 'auth/too-many-requests':
      return 'Too many failed attempts. Please try again later.';
    case 'auth/network-request-failed':
      return 'Network error. Please check your connection and try again.';
    default:
      return 'An error occurred. Please try again.';
  }
};

// Export auth instance for use in components
export { auth, db };